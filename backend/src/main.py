import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from nanoid import generate

from service.db import (
    TaskStatus,
    delete_task,
    get_all_tasks,
    get_task,
    initialize_database,
    store_result,
    update_task_status,
)
from service.health import (
    health_check_backend,
    health_check_db,
    health_check_mq,
    health_check_ollama,
    health_check_storage,
)
from service.llm import check_valid_model, get_models
from service.log import logger
from service.mq import initialize_mq, publish_task
from service.storage import get_file_url, initialize_storage, upload_file

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
        if db_init_result:
            logger.info("Database initialization successful")
        else:
            logger.error("Database initialization failed")

        logger.info("Initializing mq...")
        mq_init_result = await initialize_mq()
        if mq_init_result:
            logger.info("MQ initialization successful")
        else:
            logger.error("MQ initialization failed")

        logger.info("Initializing storage...")
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
    provider: str = Form(None),
    model: str = Form(None),
    api_key: str = Form(None),
) -> JSONResponse:
    try:
        data = await file.read()

        # Generate a unique task ID
        task_id = generate()
        basename, ext = os.path.splitext(file.filename)
        filename = f"{basename}-{task_id}{ext}"
        logger.info(f"[{task_id}] {filename} | {provider} / {model}")

        if provider and model:
            if provider != "ollama" and not api_key:
                return create_response(
                    content={"status": "error"},
                    status_code=400,
                    error_message=f"{provider}の使用にはAPIキーが必要です",
                )

            # Check if the model is valid with the provided API key
            if provider and model and api_key:
                is_valid_model = await check_valid_model(provider, model, api_key)
                if not is_valid_model:
                    return create_response(
                        content={"status": "error"},
                        status_code=404,
                        error_message="モデルが見つかりません。別のモデルを選択してください",
                    )

        # Upload the file to storage
        is_upload_success = await upload_file(
            data, f"uploads/{filename}", file.content_type
        )
        if not is_upload_success:
            return create_response(
                content={"status": "error"},
                status_code=400,
                error_message="ファイルのアップロードに失敗しました",
            )
        logger.info(f"File uploaded successfully: {filename}")

        # Prepare task data for the queue
        task_data = {
            "task_id": task_id,
            "filename": filename,
            "content_type": file.content_type,
            "original_url": get_file_url(f"uploads/{filename}"),
            "translated_url": get_file_url(f"translated/{filename}"),
            "source_lang": source_lang,
            "target_lang": target_lang,
            "provider": provider,
            "model_name": model,
            "api_key": api_key,
        }

        # Store the initial task information in the database
        is_store_result = await store_result(task_data)
        if not is_store_result:
            return create_response(
                content={"status": "error"},
                status_code=400,
                error_message="タスクの保存に失敗しました",
            )

        # Publish the task to the RabbitMQ queue
        is_publish_success = await publish_task(task_data)
        if not is_publish_success:
            await update_task_status(task_id, TaskStatus.FAILED.value)
            return create_response(
                content={"status": "error"},
                status_code=500,
                error_message="タスクのキューへの追加に失敗しました",
            )

        logger.info(f"Translation task queued successfully: {task_id}")

        return create_response(content={"status": "success", "task_id": task_id})
    except Exception as e:
        logger.error(f"Translation request error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message="タスクのキューへの追加に失敗しました",
        )


# ==================== SSE ENDPOINT FOR REAL-TIME UPDATES ====================
@app.get("/tasks/updates", tags=["api"])
async def task_updates_sse(request: Request):
    async def event_generator():
        try:
            yield 'event: connected\ndata: {"status": "connected"}\n\n'

            # Use database polling instead of direct RabbitMQ connection
            # This approach is more reliable for web clients
            last_check = {}

            while True:
                if await request.is_disconnected():
                    logger.info("Client disconnected from SSE")
                    break

                # Fetch all tasks from database
                try:
                    tasks = await get_all_tasks()

                    # Check for status changes
                    for task in tasks:
                        task_id = task.get("task_id")
                        current_status = task.get("status")

                        # If we've seen this task before and status changed, or if it's a new task
                        if (
                            task_id in last_check
                            and last_check[task_id] != current_status
                        ) or (task_id not in last_check):
                            # Send update
                            update_data = {
                                "task_id": task_id,
                                "status": current_status,
                                "timestamp": datetime.now().isoformat(),
                            }

                            yield f"event: update\ndata: {json.dumps(update_data)}\n\n"
                            logger.info(
                                f"Sent SSE update for task {task_id}: {current_status}"
                            )

                        # Update last known status
                        last_check[task_id] = current_status

                except Exception as e:
                    logger.error(f"Error fetching tasks for SSE: {str(e)}")
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

                # Wait before polling again (adjust as needed)
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"SSE error: {str(e)}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        finally:
            yield 'event: close\ndata: {"status": "disconnected"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/tasks", tags=["db"])
async def get_tasks_endpoint():
    try:
        return await get_all_tasks()
    except Exception as e:
        logger.error(f"Translation history error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message=str(e),
        )


@app.get("/task/{task_id}", tags=["db"])
async def get_task_endpoint(task_id: str):
    try:
        return await get_task(task_id)
    except Exception as e:
        logger.error(f"Translation history error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message=str(e),
        )


@app.delete("/task/{task_id}", tags=["db"])
async def delete_task_endpoint(task_id: str):
    try:
        return await delete_task(task_id)
    except Exception as e:
        logger.error(f"Translation history error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message=str(e),
        )


@app.get("/models", tags=["llm"])
async def get_models_endpoint():
    try:
        return await get_models()
    except Exception as e:
        logger.error(f"Model list error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message=str(e),
        )


# ==================== HEALTH CHECK ENDPOINTS ====================
@app.get("/health/backend", tags=["status"])
async def health_backend():
    try:
        return await health_check_backend()
    except Exception as e:
        logger.error(f"Backend health check error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message=str(e),
        )


@app.get("/health/ollama", tags=["status"])
async def health_ollama():
    try:
        return await health_check_ollama()
    except Exception as e:
        logger.error(f"Ollama health check error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message=str(e),
        )


@app.get("/health/db", tags=["status"])
async def health_db():
    try:
        return await health_check_db()
    except Exception as e:
        logger.error(f"DB health check error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message=str(e),
        )


@app.get("/health/mq", tags=["status"])
async def health_mq():
    try:
        return await health_check_mq()
    except Exception as e:
        logger.error(f"MQ health check error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message=str(e),
        )


@app.get("/health/storage", tags=["status"])
async def health_storage():
    try:
        return await health_check_storage()
    except Exception as e:
        logger.error(f"Storage health check error: {str(e)}")
        return create_response(
            content={"status": "error", "message": str(e)},
            status_code=400,
            error_message=str(e),
        )


def create_response(content, status_code=200, error_message=None):
    if error_message and status_code != 200:
        if isinstance(content, dict):
            content["error_message"] = error_message

    response = JSONResponse(
        content=content,
        status_code=status_code,
    )

    if error_message and status_code != 200:
        try:
            ascii_error = error_message.encode("ascii", errors="ignore").decode("ascii")
            if ascii_error:
                response.headers["X-LEADABLE-ERROR-MESSAGE"] = ascii_error
        except Exception as e:
            logger.error(f"Failed to set error header: {str(e)}")

    return response
