import os

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from translate import pdf_translate

app = FastAPI()


@app.post("/translate/")
async def translate_local(file: UploadFile = File(...)):
    input_pdf_data = await file.read()

    result_pdf = await pdf_translate(input_pdf_data)

    if result_pdf is None:
        return JSONResponse(status_code=400, content={"message": "Translation failed"})

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, file.filename)

    with open(output_path, "wb") as f:
        f.write(result_pdf)

    return JSONResponse(
        status_code=200, content={"message": f"File saved at {output_path}"}
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
