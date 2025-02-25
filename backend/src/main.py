import logging
import os
import base64

import model
import utils
import rabbitmq
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from translate import pdf_translate

tags_metadata = [
    {
        "name": "api",
    },
    {
        "name": "models",
    },
    {
        "name": "status",
    },
]

app = FastAPI(openapi_tags=tags_metadata)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/translate/", tags=["api"])
async def translate_local(file: UploadFile = File(...)):
    input_pdf_data = await file.read()

    # Convert bytes to base64 for JSON serialization
    pdf_data_base64 = base64.b64encode(input_pdf_data).decode()

    # Queue the translation job
    await rabbitmq.publish_message("translation_queue", {
        "pdf_data": pdf_data_base64,
        "filename": file.filename
    })

    return JSONResponse(
        status_code=202,
        content={"message": "Translation job queued", "filename": file.filename}
    )


@app.get("/download/{filename}", tags=["api"])
async def download(filename: str):
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)
    if not os.path.exists(output_path):
        return JSONResponse(status_code=404, content={"message": "File not found"})

    return FileResponse(output_path, media_type="application/pdf", filename=filename)


@app.get("/models", tags=["models"])
async def show_models():
    return await model.show_models()


@app.get("/models/{model_name}", tags=["models"])
async def download_model(model_name: str):
    return await model.download_model(utils.decode_url(model_name))


@app.get("/health", tags=["status"])
async def health_check():
    return await utils.health_check()


@app.get("/health/ollama", tags=["status"])
async def health_check_ollama():
    return await utils.health_check_ollama()
