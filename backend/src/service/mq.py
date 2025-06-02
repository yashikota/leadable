import json
import os
from enum import Enum

import redis
from bson import ObjectId
from celery import Celery

from service.log import logger


# Custom JSON encoder for MongoDB ObjectId
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Queue names
TRANSLATION_QUEUE = "translation_requests"
TASK_UPDATE_QUEUE = "task_updates"


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Celery configuration
def get_celery_app():
    redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    if REDIS_PASSWORD:
        redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

    app = Celery(
        "leadable",
        broker=redis_url,
        backend=redis_url,
    )

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Tokyo",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
    )

    return app


celery_app = get_celery_app()


def get_redis_client():
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )


async def publish_task(task_data):
    try:
        # Use celery to publish task
        celery_app.send_task(
            "worker.process_translation_task",
            args=[task_data],
            queue=TRANSLATION_QUEUE,
        )

        logger.info(f"Task {task_data.get('task_id')} published to queue")
        return True
    except Exception as e:
        logger.error(f"Failed to publish task to queue: {str(e)}")
        return False


async def publish_task_update(task_id, status, message=None):
    try:
        update_data = {
            "task_id": task_id,
            "status": status,
        }
        if message:
            update_data["message"] = message

        # Publish update to Redis
        redis_client = get_redis_client()
        channel = TASK_UPDATE_QUEUE
        redis_client.publish(channel, json.dumps(update_data, cls=MongoJSONEncoder))

        logger.info(f"Task update published for {task_id}: {status}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish task update: {str(e)}")
        return False


async def initialize_mq() -> bool:
    try:
        # Check Redis connection
        redis_client = get_redis_client()
        redis_client.ping()

        logger.info("Translation service initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize translation service: {str(e)}")
        return False
