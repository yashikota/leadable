import asyncio
import os
from enum import Enum

import pika
from pika.adapters.asyncio_connection import AsyncioConnection

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "root")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")

# Queue names
TRANSLATION_QUEUE = "translation_requests"


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
        # Add heartbeat for better connection stability
        heartbeat=600,
        blocked_connection_timeout=300,
    )


def get_rabbitmq_client():
    return pika.BlockingConnection(get_rabbitmq_connection_params())


async def get_async_rabbitmq_connection():
    future = asyncio.Future()

    def on_open(connection):
        if not future.done():
            future.set_result(connection)

    def on_error(connection, error):
        if not future.done():
            future.set_exception(Exception(f"Failed to connect to RabbitMQ: {error}"))

    # Use loop=asyncio.get_event_loop() for compatibility if needed
    AsyncioConnection(
        get_rabbitmq_connection_params(),
        on_open_callback=on_open,
        on_open_error_callback=on_error,
    )

    return await future


def ensure_queue_exists(channel, queue_name: str) -> None:
    channel.queue_declare(queue=queue_name, durable=True)


async def initialize_translation_service(translate_function=None):
    """
    Initialize the translation service and start the worker using DB persistence.
    """
    pass
