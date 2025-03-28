import asyncio
import copy
import math
import re
import string
from collections import defaultdict
from io import BytesIO
from textwrap import dedent

import fitz  # PyMuPDF
import numpy as np
import spacy
from litellm import completion
from tenacity import retry, stop_after_attempt, wait_fixed

from service.db import TaskStatus
from service.llm import convert_model, get_api_params
from service.log import logger


class TranslationService:
    supported_languages = {"en": "en_core_web_sm", "ja": "ja_core_news_sm"}
    loaded_models = {}

    def __init__(self):
        self.task_id = ""
        self.status = TaskStatus.PENDING
        self.filename = ""
        self.content_type = ""
        self.created_at = ""
        self.original_url = ""
        self.translated_url = ""
        self.source_lang = ""
        self.target_lang = ""
        self.provider = ""
        self.model_name = ""
        self.api_key = ""

        # Progress tracking
        self.length = 0
        self.count = 0
        self.is_print_progress = True

        # Temp storage fields for processing PDFs
        self.original_pdf_data = None
        self.translated_pdf_data = None
        self.block_info = None
        self.text_blocks = None
        self.fig_blocks = None
        self.excluded_blocks = None

    def load_model(self, lang_code):
        """指定された言語コードのモデルをロードする"""
        if lang_code in self.loaded_models:
            return self.loaded_models[lang_code]
        if lang_code in self.supported_languages:
            model_name = self.supported_languages[lang_code]
            try:
                nlp = spacy.load(model_name)
                self.loaded_models[lang_code] = nlp
                return nlp
            except OSError as e:
                logger.error(f"Model for '{lang_code}' could not be loaded: {e}")
                return None
        else:
            logger.info(f"No model available for language code: '{lang_code}'")
            return None

    def tokenize_text(self, lang_code, text):
        """指定された言語のテキストをトークン化し、トークンのリストを返す"""
        nlp = self.load_model(lang_code)
        if nlp:
            doc = nlp(text)
            tokens = [
                token.text for token in doc if token.is_alpha
            ]  # トークンがアルファベットで構成されているかどうかも判定
            return tokens
        else:
            return []

    async def extract_text_coordinates_dict(self, pdf_data):
        """
        pdfバイトデータのテキストファイル座標を取得します。
        """
        # PDFファイルを開く
        document = await asyncio.to_thread(fitz.open, stream=pdf_data, filetype="pdf")

        content = []
        for page_num in range(len(document)):
            # ページを取得
            page = await asyncio.to_thread(document.load_page, page_num)
            # ページからテキストブロックを取得
            text_instances_dict = await asyncio.to_thread(page.get_text, "dict")
            text_instances = text_instances_dict["blocks"]
            page_content = []

            for lines in text_instances:
                block = {}
                if lines["type"] != 0:
                    # テキストブロック以外はスキップ
                    continue
                block["page_no"] = page_num
                block["block_no"] = lines["number"]
                block["coordinates"] = lines["bbox"]
                block["text"] = ""
                sizes = []
                for line in lines["lines"]:
                    for span in line["spans"]:
                        if block["text"] == "":
                            block["text"] += span["text"]
                        else:
                            block["text"] += " " + span["text"]
                        sizes.append(span["size"])
                        block["font"] = span["font"]
                block["size"] = np.mean(sizes)
                # block["text_count"] = len(block["text"])
                page_content.append(block)

            content.append(page_content)
        await asyncio.to_thread(document.close)
        return content

    def check_first_num_tokens(self, input_list, keywords, num=2):
        for item in input_list[:num]:
            for keyword in keywords:
                if keyword.lower() in item.lower():
                    return True
        return False

    def remove_special_chars(self, text):
        return "".join(
            char
            for char in text
            if char not in string.punctuation and char not in string.digits
        )

    def calculate_token_scores(self, text_list, lang, token_threshold) -> list:
        """
        テキストのリストに対してトークン数を計算し、
        トークン数が指定されたしきい値以下の場合は0、そうでない以外の場合は1を返します。
        """
        tokens_list = [self.tokenize_text(lang, text) for text in text_list]
        token_counts = [len(tokens) for tokens in tokens_list]
        return [
            0 if count <= token_threshold else 1 for count in token_counts
        ], token_counts

    def calculate_percentile_scores(self, data) -> list:
        """
        データのパーセンタイルスコアを計算し、中央値を基準に標準化します。
        """
        item_median = np.median(data)
        item_75_percentile = np.percentile(data, 75)
        item_25_percentile = np.percentile(data, 25)
        iqr = item_75_percentile - item_25_percentile
        res = [abs((value - item_median) / iqr) if iqr != 0 else 0 for value in data]
        return res

    def calculate_marge_scores(self, scores):
        """
        トークン数、幅、サイズのスコアをマージし、合計スコアを返します。
        """
        return [sum(score_list) for score_list in scores]

    def calculate_histogram_bins(self, marge_scores, n_neighbours=0) -> tuple:
        """
        マージスコアのヒストグラムを計算し、
        最頻ビンからn_neighboursビンに相当する範囲を返します。
        0は最頻ビン1個, 1は最頻ビンの両隣を含む最大3個
        """
        # スタージェスの公式によるビン数の計算
        n = len(marge_scores)
        num_bins_sturges = math.ceil(math.log2(n) + 1)

        # Freedman-Diaconisの規則によるビン数の計算
        q75, q25 = np.percentile(marge_scores, [75, 25])
        iqr = q75 - q25
        bin_width_fd = 2 * iqr / n ** (1 / 3)
        bin_range = max(marge_scores) - min(marge_scores)
        num_bins_fd = math.ceil(bin_range / bin_width_fd)

        # 2つのビン数のうち小さい方を採用
        num_bins = min(num_bins_sturges, num_bins_fd)
        histogram, bin_edges = np.histogram(marge_scores, bins=num_bins)

        logger.info("[Histogram]")
        logger.info(f"{num_bins=}")
        logger.info(f"{histogram=}")
        logger.info(f"{bin_edges=}")

        frequent_bins = np.argsort(histogram)[::-1][: n_neighbours + 1]
        res = []
        for b in frequent_bins:
            logger.info(f"{b=}, {histogram[b]=}")
            res.append((bin_edges[b], bin_edges[b + 1]))

        logger.info(f"{res=}")
        return res

    async def remove_blocks(self, block_info, token_threshold=15, lang="en") -> list:
        """
        トークン数が指定された閾値以下のブロックをリストから削除し、
        幅300以上のパーセンタイルブロックをリストから消去します。

        :param block_info: ブロック情報のリスト
        :param token_threshold: トークンしきい値
        :return: 更新されたブロック情報のリストと削除されたブロック情報のリスト
        """
        text_blocks, fig_blocks, excluded_blocks = [], [], []

        bboxs = [item["coordinates"] for sublist in block_info for item in sublist]
        widths = [x1 - x0 for x0, _, x1, _ in bboxs]
        sizes = [item["size"] for sublist in block_info for item in sublist]
        text_list = [
            self.remove_special_chars(item["text"].replace("\n", ""))
            for sublist in block_info
            for item in sublist
        ]

        token_scores, token_counts = self.calculate_token_scores(
            text_list, lang, token_threshold
        )
        width_scores = self.calculate_percentile_scores(widths)
        size_scores = self.calculate_percentile_scores(sizes)

        scores = [[token_score] for token_score in token_scores]
        for width_score, size_score, score_list in zip(
            width_scores, size_scores, scores
        ):
            score_list.append(width_score)
            score_list.append(size_score)

        marge_scores = self.calculate_marge_scores(scores)

        frequent_bins = self.calculate_histogram_bins(
            marge_scores, n_neighbours=1
        )  # 頻度1位,2位のビンの範囲を取得
        first_bin, second_bin = frequent_bins

        i = 0
        for pages in block_info:
            page_text_blocks = []
            page_fig_table_blocks = []
            page_excluded_blocks = []

            for block in pages:
                tokens_list = self.tokenize_text(lang, block["text"])
                score = marge_scores[i]
                _simple_word_cnt = len(block["text"].split(" "))

                token_score, width_score, size_score = scores[i]

                # 本文ブロックをみなすrule（有効なTextブロック）
                rule1 = token_score == 1
                rule2 = (
                    first_bin[0] <= score <= first_bin[1]
                    or second_bin[0] <= score <= second_bin[1]
                )
                # 30単語以上かつ、空白文字の割合が40%以下
                rule3 = (
                    _simple_word_cnt > 30
                    and block["text"].count(" ") / len(block["text"]) < 0.4
                )
                is_valid_block = (rule1 and rule2) or rule3

                if self.check_first_num_tokens(
                    tokens_list, ["表", "グラフ"] if lang == "ja" else ["fig", "table"]
                ):
                    page_fig_table_blocks.append(block)
                elif is_valid_block:
                    page_text_blocks.append(block)
                else:
                    swapped_block = copy.copy(block)
                    swapped_block["text"] = (
                        f"[{score}/{is_valid_block}] /T:{token_score}/{token_counts[i]} /W:{width_score} /S:{size_score}/{sizes[i]} /Text:{block['text']}"
                    )
                    page_excluded_blocks.append(swapped_block)
                i += 1

                if is_valid_block:
                    logger.info(f"to translate: {block['text'][:20]}")
                    logger.info(f"length: {len(block['text'])}")

            text_blocks.append(page_text_blocks)
            fig_blocks.append(page_fig_table_blocks)
            excluded_blocks.append(page_excluded_blocks)

        return text_blocks, fig_blocks, excluded_blocks

    async def remove_textbox_for_pdf(self, pdf_data, remove_list):
        """
        読み込んだPDFより、すべてのテキストデータを消去します。
        leave_text_listが設定されている場合、該当リストに含まれる文字列(部分一致)は保持します。
        """
        doc = await asyncio.to_thread(fitz.open, stream=pdf_data, filetype="pdf")
        for remove_data, page in zip(remove_list, doc):
            for remove_item in remove_data:
                rect = fitz.Rect(
                    remove_item["coordinates"]
                )  # テキストブロックの領域を取得
                await asyncio.to_thread(page.add_redact_annot, rect)
            await asyncio.to_thread(
                page.apply_redactions
            )  # レダクションを適用してテキストを削除

        output_buffer = BytesIO()
        await asyncio.to_thread(
            doc.save, output_buffer, garbage=4, deflate=True, clean=True
        )
        await asyncio.to_thread(doc.close)

        output_data = output_buffer.getvalue()
        return output_data

    async def preprocess_write_blocks(self, block_info):
        lh_calc_factor = 1.3

        # フォント選択
        if self.target_lang == "en":
            font_path = "fonts/TIMES.TTF"
            a_text = "a"
        elif self.target_lang == "ja":
            font_path = "fonts/MSMINCHO.TTC"
            a_text = "あ"

        # フォントサイズを逆算+ブロックごとにテキストを分割
        any_blocks = []
        for page in block_info:
            for box in page:
                font_size = box["size"][0]

                while True:
                    # 初期化
                    max_chars_per_boxes = []

                    # フォントサイズ計算
                    font = fitz.Font("F0", font_path)
                    a_width = font.text_length(a_text, font_size)

                    # BOXに収まるテキスト数を行ごとにリストに格納
                    max_chars_per_boxes = []
                    for coordinates in box["coordinates"]:
                        x1, y1, x2, y2 = coordinates
                        hight = y2 - y1
                        width = x2 - x1

                        num_colums = int(hight / (font_size * lh_calc_factor))
                        num_raw = int(width / a_width)
                        max_chars_per_boxes.append([num_raw] * num_colums)

                    # 文字列を改行ごとに分割してリストに格納
                    text_all = box["text"].replace(
                        " ", "\u00a0"
                    )  # スペースを改行されないノーブレークスペースに置き換え
                    # text_all = box["text"]
                    text_list = text_all.split("\n")

                    text = text_list.pop(0)
                    text_num = len(text)
                    box_texts = []
                    exit_flag = False

                    for chars_per_box in max_chars_per_boxes:
                        # 各箱ごとを摘出
                        if exit_flag:
                            break
                        box_text = ""

                        for chars_per_line in chars_per_box:
                            # 1行あたりに代入できる文字数 : chars_per_line
                            if exit_flag:
                                break
                            # 行に文字を代入した際の残り文字数を計算
                            text_num = text_num - chars_per_line
                            # print(F"{chars_per_line}/{text_num}")
                            if text_num <= 0:
                                # その行にて収まる場合は、次の文字列を取り出す
                                box_text += text + "\n"
                                # print("add str to box")
                                if text_list == []:
                                    # 次の文字列がない場合はbreak
                                    exit_flag = True
                                    text = ""
                                    break
                                text = text_list.pop(0)
                                text_num = len(text)

                        if len(text) != text_num:
                            cut_length = len(text) - text_num
                            box_text += text[:cut_length]
                            text = text[cut_length:]
                        box_texts.append(box_text)
                    if text_list == [] and text == "":
                        break
                    else:
                        font_size -= 0.1
                box_texts = [text.lstrip().rstrip("\n") for text in box_texts]
                for page_no, block_no, coordinates, text in zip(
                    box["page_no"], box["block_no"], box["coordinates"], box_texts
                ):
                    result_block = {
                        "page_no": page_no,
                        "block_no": block_no,
                        "coordinates": coordinates,
                        "text": text,
                        "size": font_size,
                    }
                    any_blocks.append(result_block)
        page_groups = defaultdict(list)
        for block in any_blocks:
            page_groups[block["page_no"]].append(block)
        # 結果としてのリストのリスト
        grouped_pages = list(page_groups.values())
        return grouped_pages

    async def write_pdf_text(
        self,
        input_pdf_data,
        block_info,
        text_color=[0, 0, 0],
        font_path=None,
    ):
        """
        指定されたフォントで、文字を作画します。
        """
        lh_factor = 1.5  # 行の高さの係数

        # フォント選択
        if self.target_lang == "en" and font_path is None:
            font_path = "fonts/TIMES.TTF"
        elif self.target_lang == "ja":
            font_path = "fonts/MSMINCHO.TTC"

        doc = await asyncio.to_thread(fitz.open, stream=input_pdf_data, filetype="pdf")

        for page_block in block_info:
            for block in page_block:
                # ページ設定
                page_num = block["page_no"]
                page = doc[page_num]
                page.insert_font(fontname="F0", fontfile=font_path)
                # 書き込み実施
                coordinates = list(block["coordinates"])
                text = block["text"]
                font_size = block["size"]
                while True:
                    rect = fitz.Rect(coordinates)
                    result = page.insert_textbox(
                        rect,
                        text,
                        fontsize=font_size,
                        fontname="F0",
                        align=3,
                        lineheight=lh_factor,
                        color=text_color,
                    )
                    if result >= 0:
                        break
                    else:
                        coordinates[3] += 1

        output_buffer = BytesIO()
        await asyncio.to_thread(
            doc.save, output_buffer, garbage=4, deflate=True, clean=True
        )
        await asyncio.to_thread(doc.close)
        output_data = output_buffer.getvalue()

        return output_data

    async def create_viewing_pdf(self, base_pdf_path, translated_pdf_path):
        # PDFドキュメントを開く
        doc_base = await asyncio.to_thread(
            fitz.open, stream=base_pdf_path, filetype="pdf"
        )
        doc_translate = await asyncio.to_thread(
            fitz.open, stream=translated_pdf_path, filetype="pdf"
        )

        # 新しいPDFドキュメントを作成
        new_doc = fitz.open()

        # 各ページをループ処理
        for page_num in range(len(doc_base)):
            # base_pdfとtranslated_pdfからページを取得
            page_base = doc_base.load_page(page_num)
            page_translate = doc_translate.load_page(page_num)

            # 新しい見開きページを作成
            # ページサイズはそれぞれのPDFの1ページの幅と高さを使う
            rect_base = page_base.rect
            rect_translate = page_translate.rect

            # 両ページの高さが異なる場合、高い方に合わせる
            max_height = max(rect_base.height, rect_translate.height)

            # base_pdfのページを左ページに追加
            new_page = new_doc.new_page(width=rect_base.width, height=max_height)
            new_page.show_pdf_page(new_page.rect, doc_base, page_num)

            # translated_pdfのページを右ページに追加
            new_page = new_doc.new_page(width=rect_translate.width, height=max_height)
            new_page.show_pdf_page(new_page.rect, doc_translate, page_num)

        # ページレイアウトを見開きに設定
        new_doc.set_pagelayout("TwoPageLeft")

        # 新しいPDFファイルを保存
        output_buffer = BytesIO()
        await asyncio.to_thread(
            new_doc.save, output_buffer, garbage=4, deflate=True, clean=True
        )
        await asyncio.to_thread(new_doc.close)
        await asyncio.to_thread(doc_base.close)
        await asyncio.to_thread(doc_translate.close)
        output_data = output_buffer.getvalue()
        return output_data

    def text_pre_processing(self, text: str) -> str:
        """
        Preprocess the input text by removing extra newlines and dedenting.

        Args:
            text (str): The input text to be preprocessed.

        Returns:
            str: The preprocessed text.
        """
        _tmp = text.strip("\n")
        # replace more than 2 newlines with 2 newlines
        _tmp = re.sub(r"\n{2,}", "\n\n", _tmp)
        # _tmp = text
        _tmp = dedent(_tmp)
        return _tmp

    async def chat_with_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        print_result: bool = False,
    ) -> str:
        try:
            processed_system_prompt = self.text_pre_processing(system_prompt)
            processed_user_prompt = self.text_pre_processing(user_prompt)
            api_params = get_api_params(self.provider, self.api_key)

            response = completion(
                model=f"{convert_model(self.provider, self.model_name)}",
                messages=[
                    {"role": "system", "content": processed_system_prompt},
                    {"role": "user", "content": processed_user_prompt},
                ],
                **api_params,
            )

            self.count += 1
            logger.info(f"Progress: {self.count}/{self.length}")

            if print_result:
                logger.info(processed_user_prompt)
                logger.info(response.choices[0].message.content)
            return response.choices[0].message.content
        except Exception as e:
            return f"llm chat failed: {str(e)}"

    async def translate_str_data_with_llm(
        self,
        text: str,
        return_first_translation: bool = True,
    ) -> dict:
        if self.target_lang.lower() not in ("ja"):
            return {
                "ok": False,
                "message": "llm only supports Japanese translation",
            }

        system_prompt = "You are a world-class translator and will translate English text to Japanese."
        try:
            initial_translation = await self.chat_with_llm(
                system_prompt,
                self.text_pre_processing(
                    """
                This is a English to Japanese, Literal Translation task.
                Please provide the Japanese translation for the next sentences.
                You must not include any chat messages to the user in your response.
                ---
                {original_text}
                """.format(original_text=self.text_pre_processing(text))
                ),
                self.is_print_progress,
            )

            # Disabling self-refinement for now, as it is a time-consuming process and
            # found not to be effective in most cases.
            if return_first_translation:
                return {
                    "ok": True,
                    "data": initial_translation,
                }

            review_comment = await self.chat_with_llm(
                system_prompt,
                self.text_pre_processing(
                    """
                Orginal Text(English):
                {original_text}
                ---
                Translated Text(Japanese):
                {translated_text}
                ---
                Is there anything in the above Translated Text that does not conform to the local language's grammar, style, natural tone or cultural norms?
                Find mistakes and specify corrected phrase and why it is not appropriate.
                Each bullet should be in the following format:

                * <translated_phrase>
                    * Corrected: <corrected_phrase>
                    * Why: <reason>
                """.format(original_text=text, translated_text=initial_translation)
                ),
                self.is_print_progress,
            )

            final_translation = await self.chat_with_llm(
                system_prompt,
                self.text_pre_processing(
                    """
                Orginal Text:
                {original_text}
                ---
                Hints for translation:
                {review_comments}
                ---
                Read the Original Text, and Hits for trasnlation above, then provide complete and accurate Japanese translation.
                You must not include any chat messages to the user in your response.
                """.format(
                        original_text=text,
                        review_comments=review_comment,
                    )
                ),
                self.is_print_progress,
            )

        except Exception as e:
            return {"ok": False, "message": f"llm translation failed: {str(e)}"}

        return {
            "ok": True,
            "data": final_translation,
        }

    async def translate_blocks(self, blocks: str):
        @retry(wait=wait_fixed(2), stop=stop_after_attempt(4))
        async def translate_block(block) -> dict:
            """
            ブロックのテキストを翻訳する非同期関数
            ブロックとは、text, coordinates, block_no, page_no, sizeのキーを持つ辞書を指す
            """
            text = block["text"]
            if text.strip() == "":
                return block

            translated_text = await self.translate_str_data_with_llm(text)
            if translated_text["ok"]:
                block["text"] = translated_text["data"]
                return block
            else:
                raise Exception(translated_text["message"])

        tasks = []
        try:
            async with asyncio.TaskGroup() as tg:
                for block_idx, page in enumerate(blocks):
                    for page_idx, block in enumerate(page):
                        task = tg.create_task(translate_block(block))
                        tasks.append(((block_idx, page_idx), task))
                self.length = len(tasks)
                logger.info(f"generated {len(tasks)} tasks")
                logger.info("waiting for complete...")
        except Exception as e:
            logger.error(f"failed to create tasks: {str(e)}")
            raise e

        logger.info("completed all tasks")

        for (block_idx, page_idx), task in tasks:
            blocks[block_idx][page_idx] = task.result()

        return blocks

    async def preprocess_translation_blocks(
        self, blocks, end_maker=(".", ":", ";"), end_maker_enable=True
    ):
        """
        blockの文字列について、end makerがない場合、一括で翻訳できるように変換します。
        変換結果のblockを返します
        """
        results = []

        text = ""
        coordinates = []
        block_no = []
        page_no = []
        font_size = []

        for page in blocks:
            page_results = []
            temp_block_no = 0
            for block in page:
                text += " " + block["text"]
                page_no.append(block["page_no"])
                coordinates.append(block["coordinates"])
                block_no.append(block["block_no"])
                font_size.append(block["size"])

                if (
                    text.endswith(end_maker)
                    or block["block_no"] - temp_block_no <= 1
                    or end_maker_enable is False
                ):
                    # マーカーがある場合格納
                    page_results.append(
                        {
                            "page_no": page_no,
                            "block_no": block_no,
                            "coordinates": coordinates,
                            "text": text,
                            "size": font_size,
                        }
                    )
                    text = ""
                    coordinates = []
                    block_no = []
                    page_no = []
                    font_size = []
                temp_block_no = block["block_no"]

            results.append(page_results)
        return results

    async def pdf_translate(self):
        try:
            self.block_info = await self.extract_text_coordinates_dict(
                self.original_pdf_data
            )
            self.text_blocks, self.fig_blocks, _ = await self.remove_blocks(
                self.block_info, 10, lang=self.source_lang
            )

            # 翻訳部分を消去したPDFデータを制作
            removed_textbox_pdf_data = await self.remove_textbox_for_pdf(
                self.original_pdf_data, self.text_blocks
            )
            removed_textbox_pdf_data = await self.remove_textbox_for_pdf(
                removed_textbox_pdf_data, self.fig_blocks
            )
            logger.info("1. Generate removed_textbox_pdf_data")

            # 翻訳前のブロック準備
            preprocess_text_blocks = await self.preprocess_translation_blocks(
                self.text_blocks, (".", ":", ";"), True
            )
            preprocess_fig_blocks = await self.preprocess_translation_blocks(
                self.fig_blocks, (".", ":", ";"), False
            )
            logger.info("2. Generate Prepress_blocks")

            # 翻訳実施
            translate_text_blocks = await self.translate_blocks(preprocess_text_blocks)
            self.count = 0
            translate_fig_blocks = await self.translate_blocks(preprocess_fig_blocks)
            logger.info("3. translated blocks")

            # pdf書き込みデータ作成
            write_text_blocks = await self.preprocess_write_blocks(
                translate_text_blocks
            )
            write_fig_blocks = await self.preprocess_write_blocks(translate_fig_blocks)
            logger.info("4. Generate wirte Blocks")

            # pdfの作成
            translated_pdf_data = None
            if write_text_blocks != []:
                logger.info("write text to pdf.")
                logger.info(len(write_text_blocks))
                translated_pdf_data = await self.write_pdf_text(
                    removed_textbox_pdf_data, write_text_blocks
                )
            else:
                logger.info("write text to pdf is empty.")
                breakpoint()

            if write_fig_blocks != []:
                logger.info("write fig to pdf.")
                translated_pdf_data = await self.write_pdf_text(
                    translated_pdf_data, write_fig_blocks
                )
            else:
                logger.info("write fig to pdf is empty.")
                breakpoint()

            # 見開き結合の実施
            merged_pdf_data = await self.create_viewing_pdf(
                self.original_pdf_data, translated_pdf_data
            )
            logger.info("5. Generate PDF Data")

            # 処理完了
            self.status = TaskStatus.COMPLETED
            return True, merged_pdf_data
        except Exception as e:
            logger.error(f"pdf_translate error: {str(e)}")
            self.status = TaskStatus.FAILED
            return False, str(e)
