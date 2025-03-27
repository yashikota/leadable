import asyncio
import re
from logging import getLogger
from textwrap import dedent

from tenacity import retry, stop_after_attempt, wait_fixed

from pdf_edit import (
    create_viewing_pdf,
    extract_text_coordinates_dict,
    preprocess_write_blocks,
    remove_blocks,
    remove_textbox_for_pdf,
    write_pdf_text,
)
from service.llm import get_ollama_client

logger = getLogger(__name__)


def text_pre_processing(text: str) -> str:
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


async def chat_with_ollama(
    system_prompt: str, user_prompt: str, print_result: bool, model_name: str
) -> str:
    try:
        client = get_ollama_client()
        processed_system_prompt = text_pre_processing(system_prompt)
        processed_user_prompt = text_pre_processing(user_prompt)
        response = client.chat(
            model="gemma3:1b",
            # model=model_name,
            messages=[
                {"role": "system", "content": processed_system_prompt},
                {"role": "user", "content": processed_user_prompt},
            ],
        )
        if print_result:
            logger.info("User: \n", processed_user_prompt)
            logger.info("Ollama: \n", response["message"]["content"])
        return response["message"]["content"]
    except Exception as e:
        return f"Ollama API request failed: {str(e)}"


async def translate_str_data_with_ollama(
    text: str,
    target_lang: str,
    model_name: str,
    print_progress: bool = False,
    return_first_translation: bool = True,
) -> str:
    """Translate the input text to the target language using Ollama API."""

    if target_lang.lower() not in ("ja"):
        return {"ok": False, "message": "Ollama only supports Japanese translation."}

    system_prompt = (
        "You are a world-class translator and will translate English text to Japanese."
    )
    try:
        initial_translation = await chat_with_ollama(
            system_prompt,
            text_pre_processing(
                """
            This is a English to Japanese, Literal Translation task.
            Please provide the Japanese translation for the next sentences.
            You must not include any chat messages to the user in your response.
            ---
            {original_text}
            """.format(original_text=text_pre_processing(text))
            ),
            print_progress,
            model_name,
        )

        # Disabling self-refinement for now, as it is a time-consuming process and
        # found not to be effective in most cases.
        if return_first_translation:
            return {
                "ok": True,
                "data": initial_translation,
            }

        review_comment = await chat_with_ollama(
            system_prompt,
            text_pre_processing(
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
            print_progress,
        )

        final_translation = await chat_with_ollama(
            system_prompt,
            text_pre_processing(
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
            print_progress,
        )

    except Exception as e:
        return {"ok": False, "message": f"Ollama API request failed: {str(e)}"}

    return {
        "ok": True,
        "data": final_translation,
    }


async def translate_blocks(blocks: str, target_lang: str, model_name: str):
    @retry(wait=wait_fixed(2), stop=stop_after_attempt(4))
    async def translate_block(block) -> dict:
        """
        ブロックのテキストを翻訳する非同期関数
        ブロックとは、text, coordinates, block_no, page_no, sizeのキーを持つ辞書を指す
        """
        text = block["text"]
        if text.strip() == "":
            return block

        translated_text = await translate_str_data_with_ollama(
            text, target_lang, model_name
        )
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


async def pdf_translate(
    pdf_data: bytes, model_name: str, source_lang="en", to_lang="ja"
):
    try:
        block_info = await extract_text_coordinates_dict(pdf_data)
        text_blocks, fig_blocks, _ = await remove_blocks(
            block_info, 10, lang=source_lang
        )

        # 翻訳部分を消去したPDFデータを制作
        all_blocks = text_blocks + fig_blocks
        removed_textbox_pdf_data = await remove_textbox_for_pdf(pdf_data, all_blocks)
        logger.info("1. Generate removed_textbox_pdf_data")

        # 翻訳前のブロック準備
        preprocess_all_blocks = await preprocess_translation_blocks(
            all_blocks, (".", ":", ";"), True
        )
        logger.info("2. Generate Prepress_blocks")

        # 翻訳実施
        translated_all_blocks = await translate_blocks(
            preprocess_all_blocks, to_lang, model_name
        )
        logger.info("3. translated blocks")

        # pdf書き込みデータ作成
        write_all_blocks = await preprocess_write_blocks(translated_all_blocks, to_lang)
        logger.info("4. Generate wirte Blocks")

        # pdfの作成
        translated_pdf_data = None
        if write_all_blocks != []:
            logger.info("write text to pdf")
            logger.info(len(write_all_blocks))
            translated_pdf_data = await write_pdf_text(
                removed_textbox_pdf_data, write_all_blocks, to_lang
            )
        else:
            logger.info("write text to pdf is empty")
            breakpoint()

        # 見開き結合の実施
        merged_pdf_data = await create_viewing_pdf(pdf_data, translated_pdf_data)
        logger.info("5. Generate PDF Data")

        return True, merged_pdf_data
    except Exception as e:
        logger.error(f"pdf_translate error: {str(e)}")
        return False, str(e)
