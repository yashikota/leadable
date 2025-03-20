import urllib.parse
import urllib.request
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def decode_url(url: str) -> str:
    return urllib.parse.unquote(url)


async def health_check_backend():
    """Health check for the backend service."""
    return {"status": "ok"}


async def health_check_ollama():
    """Health check for the Ollama service."""
    try:
        # Import here to avoid circular imports
        from backend.src.service.llm import OLLAMA_HOST_URL as url
        urllib.request.urlopen(url).close()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Ollama health check failed: {str(e)}")
        return {"status": "error", "error": str(e)}


async def health_check_db():
    """Health check for the database service."""
    try:
        # Import here to avoid circular imports
        from backend.src.service.db import get_mongo_client, MONGO_DB
        client = get_mongo_client()
        db = client[MONGO_DB]
        _ = db.list_collection_names()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {"status": "error", "error": str(e)}


async def health_check_mq():
    """Health check for the message queue service."""
    try:
        # Import here to avoid circular imports
        from backend.src.service.mq import get_rabbitmq_connection
        connection = get_rabbitmq_connection()
        _ = connection.channel()
        connection.close()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Message queue health check failed: {str(e)}")
        return {"status": "error", "error": str(e)}
