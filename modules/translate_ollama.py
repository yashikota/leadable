import re
import ollama
from textwrap import dedent

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


async def chat_with_ollama(system_prompt: str, user_prompt: str, print_result: bool) -> str:
    try:
        processed_system_prompt = text_pre_processing(system_prompt)
        processed_user_prompt = text_pre_processing(user_prompt)
        response = ollama.chat(
            model="gemma2:27b",  # specify the model that supports chat completions
            messages=[
                {"role": "system", "content": processed_system_prompt},
                {"role": "user", "content": processed_user_prompt}
            ]
        )
        if print_result:
            print("=*"*20)
            print("User: \n", processed_user_prompt)
            print("Ollama: \n", response["message"]["content"])
        return response["message"]["content"]
    except Exception as e:
        return f"Ollama API request failed: {str(e)}"


async def translate_str_data_with_ollama(
        text: str,
        target_lang: str,
        print_progress: bool = False,
        return_first_translation: bool = True
    ) -> str:
    """Translate the input text to the target language using Ollama API.
    """

    if target_lang.lower() not in ("ja"):
        return {'ok': False, 'message': "Ollama only supports Japanese translation."}

    system_prompt = "You are a world-class translator and will translate English text to Japanese."
    try:
        initial_translation = await chat_with_ollama(
            system_prompt,
            """
            This is a English to Japanese, Literal Translation task. Please provide the Japanese translation for the next sentences.
            You must not include any chat messages to the user in your response.
            ---
            {original_text}
            """.format(original_text=text_pre_processing(text)), print_progress)

        #TODO! 後で消す
        if return_first_translation:
            return {
                'ok': True,
                'data': initial_translation,
            }

        # Let's work this out in a step by step way to be sure we have the right answer.
        review_comment = await chat_with_ollama(
        # review_comment = await chat_with_openai(
            system_prompt,
            """
            Is there anything in this Translated Text that does not conform to the local language? Find the mistakes and correct them.
            ---
            Orginal Text:
            {original_text}
            ---
            Translated Text:
            {translated_text}
            """.format(
                original_text=text_pre_processing(text),
                translated_text=text_pre_processing(initial_translation)
            ), print_progress)


        final_translation = await chat_with_ollama(
            system_prompt,
            """
            Read the Original Text, Initial Translation and Review Comments, then provide corrected **full text** of translation.
            The final translation should be a complete and accurate translation of the original text.
            You must not include any chat messages to the user in your response.
            ---
            Orginal Text:
            {original_text}
            ---
            Translated Text:
            {translated_text}
            ---
            Review Comments:
            {review_comments}
            """.format(
                original_text=text,
                translated_text=text_pre_processing(initial_translation),
                review_comments=text_pre_processing(review_comment),
            ), print_progress)

    except Exception as e:
        return {'ok': False, 'message': f"Ollama API request failed: {str(e)}"}

    return {
        'ok': True,
        'data': final_translation,
        # 'progress': {
        #     '01_init': initial_translation,
        #     '02_review': review_comment,
        #     '03_final': final_translation
        # }
    }