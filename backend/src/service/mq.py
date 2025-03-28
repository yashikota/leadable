import asyncio
import json
import os
from enum import Enum

import pika
from bson import ObjectId
from pika.adapters.asyncio_connection import AsyncioConnection

from service.log import logger


# Custom JSON encoder for MongoDB ObjectId
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "root")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")

# Queue names
TRANSLATION_QUEUE = "translation_requests"
TASK_UPDATE_QUEUE = "task_updates"


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def get_rabbitmq_connection_params() -> pika.ConnectionParameters:
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    return pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        virtual_host=RABBITMQ_VHOST,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )


def get_rabbitmq_client():
    return pika.BlockingConnection(get_rabbitmq_connection_params())


async def get_rabbitmq_connection():
    future = asyncio.Future()

    def on_open(connection):
        if not future.done():
            future.set_result(connection)

    def on_error(connection, error):
        if not future.done():
            future.set_exception(Exception(f"Failed to connect to RabbitMQ: {error}"))

    AsyncioConnection(
        get_rabbitmq_connection_params(),
        on_open_callback=on_open,
        on_open_error_callback=on_error,
    )

    return await future


def ensure_queue_exists(channel, queue_name: str) -> None:
    channel.queue_declare(queue=queue_name, durable=True)


async def publish_task(task_data):
    try:
        connection = get_rabbitmq_client()
        channel = connection.channel()
        ensure_queue_exists(channel, TRANSLATION_QUEUE)

        channel.basic_publish(
            exchange="",
            routing_key=TRANSLATION_QUEUE,
            body=json.dumps(task_data, cls=MongoJSONEncoder),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
        connection.close()
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

        connection = get_rabbitmq_client()
        channel = connection.channel()

        ensure_queue_exists(channel, TASK_UPDATE_QUEUE)

        channel.basic_publish(
            exchange="",
            routing_key=TASK_UPDATE_QUEUE,
            body=json.dumps(update_data, cls=MongoJSONEncoder),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )

        connection.close()
        logger.info(f"Task update published for {task_id}: {status}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish task update: {str(e)}")
        return False


async def initialize_mq() -> bool:
    try:
        connection = get_rabbitmq_client()
        channel = connection.channel()

        ensure_queue_exists(channel, TRANSLATION_QUEUE)
        ensure_queue_exists(channel, TASK_UPDATE_QUEUE)

        connection.close()
        logger.info("Translation service initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize translation service: {str(e)}")
        return False
