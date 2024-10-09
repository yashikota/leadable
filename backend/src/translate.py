import asyncio

from pdf_edit import (create_viewing_pdf, extract_text_coordinates_dict,
                      preprocess_write_blocks, remove_blocks,
                      remove_textbox_for_pdf, write_pdf_text)
from tenacity import retry, stop_after_attempt, wait_fixed
from translate_ollama import translate_str_data_with_ollama


async def translate_blocks(blocks: str, target_lang: str):
    @retry(wait=wait_fixed(2), stop=stop_after_attempt(4))
    async def translate_block(block) -> dict:
        """
        ブロックのテキストを翻訳する非同期関数
        ブロックとは、text, coordinates, block_no, page_no, sizeのキーを持つ辞書を指す
        """
        text = block["text"]
        if text.strip() == "":
            return block

        translated_text = await translate_str_data_with_ollama(text, target_lang)
        if translated_text["ok"]:
            block["text"] = translated_text["data"]
            return block
        else:
            raise Exception(translated_text["message"])

    def print_progress():
        """
        翻訳進捗状況表示
        """
        print(".", end="", flush=True)

    tasks = []
    try:
        async with asyncio.TaskGroup() as tg:
            for block_idx, page in enumerate(blocks):
                for page_idx, block in enumerate(page):
                    task = tg.create_task(translate_block(block))
                    task.add_done_callback(print_progress)
                    tasks.append(((block_idx, page_idx), task))
            print(f"generated {len(tasks)} tasks")
            print("waiting for complete...")
            # show progress while waiting for completion
    except Exception as e:
        print(f"{e.exceptions=}")
        raise e

    print("completed all tasks")

    for (block_idx, page_idx), task in tasks:
        blocks[block_idx][page_idx] = task.result()

    return blocks


async def preprocess_translation_blocks(
    blocks, end_maker=(".", ":", ";"), end_maker_enable=True
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
                or end_maker_enable == False
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


async def pdf_translate(pdf_data, source_lang="en", to_lang="ja"):
    block_info = await extract_text_coordinates_dict(pdf_data)
    text_blocks, fig_blocks, _ = await remove_blocks(block_info, 10, lang=source_lang)

    # 翻訳部分を消去したPDFデータを制作
    removed_textbox_pdf_data = await remove_textbox_for_pdf(pdf_data, text_blocks)
    removed_textbox_pdf_data = await remove_textbox_for_pdf(
        removed_textbox_pdf_data, fig_blocks
    )
    print("1. Generate removed_textbox_pdf_data")

    # 翻訳前のブロック準備
    preprocess_text_blocks = await preprocess_translation_blocks(
        text_blocks, (".", ":", ";"), True
    )
    preprocess_fig_blocks = await preprocess_translation_blocks(
        fig_blocks, (".", ":", ";"), False
    )
    print("2. Generate Prepress_blocks")

    # 翻訳実施
    translate_text_blocks = await translate_blocks(preprocess_text_blocks, to_lang)
    translate_fig_blocks = await translate_blocks(preprocess_fig_blocks, to_lang)
    print("3. translated blocks")

    # pdf書き込みデータ作成
    write_text_blocks = await preprocess_write_blocks(translate_text_blocks, to_lang)
    write_fig_blocks = await preprocess_write_blocks(translate_fig_blocks, to_lang)
    print("4. Generate wirte Blocks")

    # pdfの作成
    translated_pdf_data = None
    if write_text_blocks != []:
        print("write text to pdf.")
        print(len(write_text_blocks))
        translated_pdf_data = await write_pdf_text(
            removed_textbox_pdf_data, write_text_blocks, to_lang
        )
    else:
        print("write text to pdf is empty.")
        breakpoint()

    if write_fig_blocks != []:
        print("write fig to pdf.")
        translated_pdf_data = await write_pdf_text(
            translated_pdf_data, write_fig_blocks, to_lang
        )
    else:
        print("write fig to pdf is empty.")
        breakpoint()

    # 見開き結合の実施
    marged_pdf_data = await create_viewing_pdf(pdf_data, translated_pdf_data)
    print("5. Generate PDF Data")

    return marged_pdf_data
