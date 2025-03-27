from logging import getLogger

from service.db import MONGO_DB, get_mongo_client
from service.llm import get_ollama_client
from service.mq import get_rabbitmq_client
from service.storage import DEFAULT_BUCKET, get_minio_client

logger = getLogger(__name__)


async def health_check_backend():
    return {"status": "ok"}


async def health_check_ollama():
    try:
        client = get_ollama_client()
        client.ps()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Ollama health check failed: {str(e)}")
        return {"status": "error", "error": str(e)}


async def health_check_db():
    try:
        client = get_mongo_client()
        db = client[MONGO_DB]
        db.list_collection_names()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {"status": "error", "error": str(e)}


async def health_check_mq():
    try:
        connection = get_rabbitmq_client()
        connection.channel()
        connection.close()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Message queue health check failed: {str(e)}")
        return {"status": "error", "error": str(e)}


async def health_check_storage():
    try:
        client = get_minio_client()
        client.bucket_exists(DEFAULT_BUCKET)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Storage health check failed: {str(e)}")
        return {"status": "error", "error": str(e)}
