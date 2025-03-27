import os
from contextlib import asynccontextmanager
from datetime import datetime
from logging import getLogger

from discord_webhook import DiscordWebhook
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from service.db import (
    delete_task,
    get_all_tasks,
    get_task,
    initialize_database,
    store_result,
)
from service.health import (
    health_check_backend,
    health_check_db,
    health_check_mq,
    health_check_ollama,
    health_check_storage,
)
from service.llm import show_models
from service.storage import get_file_url, initialize_storage, upload_file

logger = getLogger(__name__)

tags_metadata = [
    {"name": "api"},
    {"name": "db"},
    {"name": "llm"},
    {"name": "status"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing services...")
    try:
        logger.info("Initializing database...")
        db_init_result = initialize_database()
        if db_init_result.get("status") == "error":
            logger.error(
                f"Database initialization failed: {db_init_result.get('message')}"
            )
        else:
            logger.info(f"Database initialization result: {db_init_result}")

        # try:
        #     logger.info("Initializing translation service...")
        #     mq_init_result = await initialize_translation_service(custom_translate_function)
        #     logger.info(f"Translation service initialization result: {mq_init_result}")
        # except Exception as e:
        #     logger.error(f"Translation service initialization failed: {str(e)}")
        #     logger.warning("Application will continue without translation service")

        logger.info("Initialization storage...")
        storage_init_result = initialize_storage()
        if storage_init_result:
            logger.info("Storage initialization successful")
        else:
            logger.error("Storage initialization failed")

        logger.info("All services initialized successfully")
    except Exception as e:
        logger.error(f"Error during initialization: {str(e)}")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Leadable",
    description="Leadable API",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== MAIN ENDPOINTS ====================
@app.post("/translate", tags=["api"])
async def translate_endpoint(
    source_lang: str = Form("en"),
    target_lang: str = Form("ja"),
    file: UploadFile = File(...),
    model_name: str = Form(None),
) -> JSONResponse:
    try:
        data = await file.read()

        # Upload the file to storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename, ext = os.path.splitext(file.filename)
        filename = f"{basename}-{timestamp}{ext}"
        is_upload_success = await upload_file(
            data, f"uploads/{filename}", file.content_type
        )
        if not is_upload_success:
            return JSONResponse(
                status_code=400, content={"message": "Uploaded File upload failed"}
            )
        original_file = {
            "filename": file.filename,
            "url": get_file_url(f"uploads/{filename}"),
        }

        # Translate the PDF file
        # is_translate_success, result_pdf = await pdf_translate(
        #     data, model_name=model_name
        # )
        # if not is_translate_success:
        #     return JSONResponse(
        #         status_code=400, content={"message": "Translation failed"}
        #     )
        is_upload_success = await upload_file(
            data, f"translated/{filename}", file.content_type
        )
        if not is_upload_success:
            return JSONResponse(
                status_code=400, content={"message": "Translated File upload failed"}
            )
        translated_file = {
            "filename": file.filename,
            "url": get_file_url(f"translated/{filename}"),
        }

        # Store the translation result
        task_id = await store_result(original_file, translated_file)

        # Discord Webhook
        if discord_webhook_url := os.getenv("DISCORD_WEBHOOK_URL"):
            webhook = DiscordWebhook(
                url=discord_webhook_url,
                content=f"翻訳が終了しました！ [{filename}]({get_file_url(f'translated/{filename}')})",
            )
            response = webhook.execute()
            logger.info(f"Discord Webhook response: {response}")

        return JSONResponse(status_code=200, content={"task_id": task_id})
    except Exception as e:
        logger.error(f"Translation request error: {str(e)}")
        return JSONResponse(status_code=400, content={"message": "Translation failed"})


@app.get("/tasks", tags=["db"])
async def get_tasks_endpoint():
    try:
        return await get_all_tasks()
    except Exception as e:
        logger.error(f"Translation history error: {str(e)}")
        return {
            "error": str(e),
        }


@app.get("/task/{task_id}", tags=["db"])
async def get_task_endpoint(task_id: str):
    try:
        return await get_task(task_id)
    except Exception as e:
        logger.error(f"Translation history error: {str(e)}")
        return {
            "error": str(e),
        }


@app.delete("/task/{task_id}", tags=["db"])
async def delete_task_endpoint(task_id: str):
    try:
        return await delete_task(task_id)
    except Exception as e:
        logger.error(f"Translation history error: {str(e)}")
        return {
            "error": str(e),
        }


@app.get("/models", tags=["llm"])
async def models():
    try:
        return await show_models()
    except Exception as e:
        logger.error(f"Model list error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get model list",
        }


# ==================== HEALTH CHECK ENDPOINTS ====================
@app.get("/health/backend", tags=["status"])
async def health_backend():
    try:
        return await health_check_backend()
    except Exception as e:
        logger.error(f"Backend health check error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.get("/health/ollama", tags=["status"])
async def health_ollama():
    try:
        return await health_check_ollama()
    except Exception as e:
        logger.error(f"Ollama health check error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.get("/health/db", tags=["status"])
async def health_db():
    try:
        return await health_check_db()
    except Exception as e:
        logger.error(f"DB health check error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.get("/health/mq", tags=["status"])
async def health_mq():
    try:
        return await health_check_mq()
    except Exception as e:
        logger.error(f"MQ health check error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.get("/health/storage", tags=["status"])
async def health_storage():
    try:
        return await health_check_storage()
    except Exception as e:
        logger.error(f"Storage health check error: {str(e)}")
        return {"status": "error", "message": str(e)}
