import logging
import os
import asyncio
from pathlib import Path
import tempfile
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.responses import StreamingResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define metadata for API documentation
tags_metadata = [
    {"name": "api"},
    {"name": "models"},
    {"name": "status"},
]


# Create lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services
    logger.info("Initializing services...")
    try:
        # Import services here to avoid circular imports
        from backend.src.service.db import initialize_database
        from backend.src.service.mq import initialize_translation_service

        # Initialize database first - with error handling
        logger.info("Initializing database...")
        db_init_result = await initialize_database()
        logger.info(f"Database initialization result: {db_init_result}")

        # Then initialize translation service
        logger.info("Initializing translation service...")
        # Import the function only when needed
        from backend.src.main import custom_translate_function
        mq_init_result = await initialize_translation_service(custom_translate_function)
        logger.info(f"Translation service initialization result: {mq_init_result}")

        logger.info("All services initialized successfully")
    except Exception as e:
        # Log but don't crash - allow app to start anyway
        logger.error(f"Error during initialization: {str(e)}")

    yield  # App runs here

    # Shutdown: Clean up resources if needed
    logger.info("Shutting down...")


# Initialize FastAPI with lifespan
app = FastAPI(
    title="Translation API",
    description="API for file upload, translation, and download",
    lifespan=lifespan,
    openapi_tags=tags_metadata
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== CUSTOM TRANSLATION FUNCTION ====================
async def custom_translate_function(
    source_text: str, source_lang: str, target_lang: str
) -> str:
    """
    Custom translation function that uses Ollama's LLM for translation.
    This will be passed to the translation worker.
    """
    try:
        # Import here to avoid potential circular imports
        from backend.src.service.storage import download_file
        from backend.src.service.llm import get_ollama_client

        # Check if the source_text is a MinIO file path
        if source_text.startswith("file://"):
            file_path = source_text[7:]  # Remove file:// prefix

            # Download the content from MinIO
            file_content = download_file(file_path)

            if isinstance(file_content, bytes):
                source_text = file_content.decode("utf-8")
            else:
                # If download_file returned a file path
                with open(file_content, "r", encoding="utf-8") as f:
                    source_text = f.read()

        # Format prompt for the translation model
        system_prompt = f"You are a professional translator. Translate the following text from {source_lang} to {target_lang}."
        prompt = f"Translate the following text from {source_lang} to {target_lang}:\n\n{source_text}"

        # Get the Ollama client
        client = get_ollama_client()

        # Call the LLM for translation
        response = client.generate(
            model="llama3",  # or any other model
            prompt=prompt,
            system=system_prompt,
            options={"temperature": 0.3}
        )

        translated_text = response.get("response", "")
        return translated_text.strip()
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        raise Exception(f"Translation error: {str(e)}")


# ==================== HEALTH CHECK ENDPOINTS ====================
@app.get("/health/backend")
async def health_backend():
    """Health check for the backend service"""
    return {"status": "ok"}


@app.get("/health/ollama")
async def health_ollama():
    """Health check for the Ollama service"""
    try:
        from backend.src.utils import health_check_ollama
        return await health_check_ollama()
    except Exception as e:
        logger.error(f"Ollama health check error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.get("/health/db")
async def health_db():
    """Health check for the database service"""
    try:
        from backend.src.utils import health_check_db
        return await health_check_db()
    except Exception as e:
        logger.error(f"DB health check error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.get("/health/mq")
async def health_mq():
    """Health check for the message queue service"""
    try:
        from backend.src.utils import health_check_mq
        return await health_check_mq()
    except Exception as e:
        logger.error(f"MQ health check error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health_all():
    """Health check for all services"""
    backend = {"status": "ok"}

    try:
        from backend.src.utils import health_check_ollama, health_check_db, health_check_mq
        ollama = await health_check_ollama()
        db = await health_check_db()
        mq = await health_check_mq()
    except Exception as e:
        logger.error(f"Health checks error: {str(e)}")
        ollama = {"status": "error", "message": "Service unavailable"}
        db = {"status": "error", "message": "Service unavailable"}
        mq = {"status": "error", "message": "Service unavailable"}

    return {
        "backend": backend,
        "ollama": ollama,
        "db": db,
        "mq": mq,
    }


# ==================== FILE UPLOAD ENDPOINTS ====================
@app.post("/upload/file")
async def upload_file_endpoint(file: UploadFile = File(...)):
    """Upload a file to MinIO storage."""
    try:
        # Import here to avoid potential circular imports
        from backend.src.service.storage import upload_file

        # Generate a unique object name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_filename = file.filename or "unnamed_file"
        object_name = f"uploads/{timestamp}_{original_filename}"

        # Read file content
        file_content = await file.read()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            # Upload file to MinIO
            upload_file(
                file_path_or_object=temp_file_path,
                object_name=object_name,
                content_type=file.content_type,
            )

            return {
                "success": True,
                "filename": original_filename,
                "object_name": object_name,
                "message": "File uploaded successfully",
            }
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return {"success": False, "error": str(e), "message": "Failed to upload file"}


@app.post("/translate")
async def translate_file(
    source_lang: str = Form("en"),
    target_lang: str = Form("ja"),
    file: UploadFile = File(...),
):
    """Submit a file translation request."""
    try:
        # Import here to avoid potential circular imports
        from backend.src.service.mq import submit_translation_request

        # First upload the file to MinIO
        upload_result = await upload_file_endpoint(file)

        if not upload_result.get("success", False):
            return upload_result

        # Create a file reference URL
        file_url = f"file://{upload_result['object_name']}"

        # Submit translation request with file reference
        result = await submit_translation_request(
            source_text=file_url, source_lang=source_lang, target_lang=target_lang
        )

        # Add file info to result
        result["original_file"] = upload_result["filename"]
        result["object_name"] = upload_result["object_name"]

        return result
    except Exception as e:
        logger.error(f"Translation request error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to submit file translation request"
        }


@app.get("/translate/status/{task_id}")
async def get_status(task_id: str):
    """Get the status of a translation task."""
    try:
        # Import here to avoid potential circular imports
        from backend.src.service.mq import get_translation_status
        return await get_translation_status(task_id)
    except Exception as e:
        logger.error(f"Status check error for task {task_id}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get translation status",
        }


@app.get("/translate/status")
async def get_all_statuses():
    """Get the status of all translation tasks."""
    try:
        # Import here to avoid potential circular imports
        from backend.src.service.mq import get_all_translation_statuses
        return await get_all_translation_statuses()
    except Exception as e:
        logger.error(f"Status list error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get translation statuses",
        }


# ==================== HISTORY & DOWNLOAD ENDPOINTS ====================
@app.get("/translations/history")
async def get_translations(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
):
    """Get translation history with pagination."""
    try:
        # Import here to avoid potential circular imports
        from backend.src.service.db import get_translation_history
        return await get_translation_history(limit=limit, skip=skip, search_text=search)
    except Exception as e:
        logger.error(f"Translation history error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get translation history",
        }


@app.get("/download/{task_id}")
async def download_translation(task_id: str):
    """Download a translated file by task ID."""
    try:
        # Import here to avoid potential circular imports
        from backend.src.service.mq import get_translation_status, TaskStatus
        from backend.src.service.storage import download_file

        # Get translation details
        translation = await get_translation_status(task_id)

        if translation.get("status") != TaskStatus.COMPLETED.value:
            return {
                "success": False,
                "message": f"Translation not completed. Current status: {translation.get('status')}",
            }

        result = translation.get("result")

        if not result:
            return {"success": False, "message": "Translation result not found"}

        # Check if result is a file reference
        if result.startswith("file://"):
            file_path = result[7:]  # Remove file:// prefix
            return StreamingResponse(
                download_file(file_path),
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f"attachment; filename=translated_{Path(file_path).name}"
                },
            )

        # For text translations, create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
            temp_file.write(result.encode("utf-8"))
            temp_file_path = temp_file.name

        try:
            return FileResponse(
                temp_file_path,
                filename=f"translation_{task_id}.txt",
                media_type="text/plain",
            )
        finally:
            # Schedule file deletion after response is sent
            # (FileResponse will serve the file and then the cleanup will happen)
            # Note: In FastAPI background deletion would be better but keeping it simple
            asyncio.create_task(delete_file_later(temp_file_path))
    except Exception as e:
        logger.error(f"Download error for task {task_id}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to download translation",
        }


async def delete_file_later(file_path: str, delay: float = 60):
    """Delete a file after a delay."""
    await asyncio.sleep(delay)
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception:
        pass  # Silently ignore deletion errors
