import os
import json
import asyncio
import logging
from datetime import datetime
import pika
from pika.adapters.asyncio_connection import AsyncioConnection
from enum import Enum

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")

# Queue names
TRANSLATION_QUEUE = "translation_requests"
STATUS_QUEUE = "translation_status"

# Status tracker (in-memory for simplicity, consider using a database in production)
translation_tasks = {}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Enum for task status values"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def get_rabbitmq_connection_params() -> pika.ConnectionParameters:
    """
    Get RabbitMQ connection parameters.
    """
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    return pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        virtual_host=RABBITMQ_VHOST,
        credentials=credentials,
    )


def get_rabbitmq_connection():
    """
    Get a blocking connection to RabbitMQ.
    """
    return pika.BlockingConnection(get_rabbitmq_connection_params())


async def get_async_rabbitmq_connection():
    """
    Get an asynchronous connection to RabbitMQ.
    """
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
    """
    Ensure that the specified queue exists, creating it if necessary.
    """
    channel.queue_declare(queue=queue_name, durable=True)


async def submit_translation_request(
    source_text: str,
    source_lang: str = "auto",
    target_lang: str = "en",
    priority: int = 0,
) -> dict:
    """
    Submit a translation request to the queue.

    Args:
        source_text: Text to translate
        source_lang: Source language code (or "auto" for auto-detection)
        target_lang: Target language code
        priority: Priority of the request (higher number = higher priority)

    Returns:
        Dictionary with task_id and status information
    """
    try:
        # Generate a unique task ID
        task_id = f"translation_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(source_text) % 10000}"

        # Prepare the message
        message = {
            "task_id": task_id,
            "source_text": source_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "timestamp": datetime.now().isoformat(),
        }

        # Get a connection and channel
        connection = get_rabbitmq_connection()
        channel = connection.channel()

        # Ensure queues exist
        ensure_queue_exists(channel, TRANSLATION_QUEUE)
        ensure_queue_exists(channel, STATUS_QUEUE)

        # Add task to tracking
        translation_tasks[task_id] = {
            "status": TaskStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "source_lang": source_lang,
            "target_lang": target_lang,
            "source_text": source_text,
            "result": None,
        }

        # Publish status update
        channel.basic_publish(
            exchange="",
            routing_key=STATUS_QUEUE,
            body=json.dumps(
                {
                    "task_id": task_id,
                    "status": TaskStatus.PENDING.value,
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            ),
        )

        # Publish translation request
        channel.basic_publish(
            exchange="",
            routing_key=TRANSLATION_QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                priority=priority,
            ),
        )

        connection.close()

        return {
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
            "message": "Translation request submitted successfully",
        }

    except Exception as e:
        logger.error(f"Error submitting translation request: {str(e)}")
        return {"error": str(e), "message": "Failed to submit translation request"}


async def get_translation_status(task_id: str) -> dict:
    """
    Get the status of a translation task.

    Args:
        task_id: ID of the translation task

    Returns:
        Dictionary with status information
    """
    if task_id in translation_tasks:
        return {"task_id": task_id, **translation_tasks[task_id]}
    else:
        return {
            "task_id": task_id,
            "status": "not_found",
            "message": "Translation task not found",
        }


async def get_all_translation_statuses() -> list:
    """
    Get the status of all translation tasks.

    Returns:
        List of dictionaries with status information
    """
    return [
        {"task_id": task_id, **task_data}
        for task_id, task_data in translation_tasks.items()
    ]


async def update_translation_status(
    task_id: str, status: str, result: str = None
) -> dict:
    """
    Update the status of a translation task.

    Args:
        task_id: ID of the translation task
        status: New status
        result: Translation result (if completed)

    Returns:
        Dictionary with updated status information
    """
    if task_id in translation_tasks:
        translation_tasks[task_id]["status"] = status
        translation_tasks[task_id]["updated_at"] = datetime.now().isoformat()

        if result is not None:
            translation_tasks[task_id]["result"] = result

        # Publish status update
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            ensure_queue_exists(channel, STATUS_QUEUE)

            channel.basic_publish(
                exchange="",
                routing_key=STATUS_QUEUE,
                body=json.dumps(
                    {
                        "task_id": task_id,
                        "status": status,
                        "timestamp": datetime.now().isoformat(),
                        "result": result,
                    }
                ),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                ),
            )

            connection.close()
        except Exception as e:
            logger.error(f"Error publishing status update: {str(e)}")

        return {
            "task_id": task_id,
            "status": status,
            "message": "Translation status updated successfully",
        }
    else:
        return {
            "task_id": task_id,
            "status": "not_found",
            "message": "Translation task not found",
        }


async def start_translation_worker(translate_function) -> None:
    """
    Start a worker to process translation requests one at a time.

    Args:
        translate_function: Async function that performs the actual translation.
                          It should accept source_text, source_lang, and target_lang parameters.
    """
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        ensure_queue_exists(channel, TRANSLATION_QUEUE)

        # Set QoS to process only one message at a time
        channel.basic_qos(prefetch_count=1)

        async def process_message(ch, method, properties, body):
            try:
                # Parse the message
                message = json.loads(body)
                task_id = message.get("task_id")
                source_text = message.get("source_text")
                source_lang = message.get("source_lang", "auto")
                target_lang = message.get("target_lang", "en")

                logger.info(f"Processing translation task {task_id}")

                # Update status to processing
                await update_translation_status(task_id, TaskStatus.PROCESSING.value)

                # Perform the translation
                try:
                    translated_text = await translate_function(
                        source_text=source_text,
                        source_lang=source_lang,
                        target_lang=target_lang,
                    )

                    # Update status to completed with result
                    await update_translation_status(
                        task_id, TaskStatus.COMPLETED.value, result=translated_text
                    )

                except Exception as e:
                    logger.error(f"Translation error for task {task_id}: {str(e)}")
                    await update_translation_status(
                        task_id,
                        TaskStatus.FAILED.value,
                        result=f"Translation error: {str(e)}",
                    )

                # Acknowledge the message
                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                # Reject the message and requeue it
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        # Set up the consumer
        channel.basic_consume(
            queue=TRANSLATION_QUEUE,
            on_message_callback=lambda ch, method, props, body: asyncio.run(
                process_message(ch, method, props, body)
            ),
        )

        logger.info("Translation worker started. Waiting for messages...")
        channel.start_consuming()

    except Exception as e:
        logger.error(f"Worker error: {str(e)}")
        # Try to restart the worker after a delay
        await asyncio.sleep(5)
        await start_translation_worker(translate_function)


# Example of a translation function to be passed to the worker
async def example_translate_function(
    source_text: str, source_lang: str, target_lang: str
) -> str:
    """
    Example translation function. Replace with actual translation implementation.
    """
    # Simulate translation delay
    await asyncio.sleep(2)
    return f"Translated from {source_lang} to {target_lang}: {source_text}"


# Function to initialize and start a translation worker
async def initialize_translation_service(translate_function=None):
    """
    Initialize the translation service and start a worker.

    Args:
        translate_function: Function to use for translation (if None, uses example_translate_function)
    """
    if translate_function is None:
        translate_function = example_translate_function

    # Start the worker in a separate task
    asyncio.create_task(start_translation_worker(translate_function))

    logger.info("Translation service initialized")
    return {
        "status": "initialized",
        "message": "Translation service started successfully",
    }
