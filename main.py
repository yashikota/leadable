import asyncio
import os

from modules.translate import pdf_translate


async def translate_local():
    file_name = "test.pdf"
    file_path = os.path.join("testdata", file_name)

    with open(file_path, "rb") as f:
        input_pdf_data = f.read()

    result_pdf = await pdf_translate(input_pdf_data)

    if result_pdf is None:
        return

    _, file_name = os.path.split(file_path)
    output_path = os.path.join("output", file_name)

    os.makedirs("output", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(result_pdf)


if __name__ == "__main__":
    asyncio.run(translate_local())
