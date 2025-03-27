import asyncio
import json
import os
from datetime import datetime
from enum import Enum
from logging import getLogger

import pika
from pika.adapters.asyncio_connection import AsyncioConnection

from service.db import (
    create_task_status,
    get_all_task_statuses,
    get_task_status,
    save_translation_result,
    update_task_status,
)

logger = getLogger(__name__)

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "root")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")

# Queue names
TRANSLATION_QUEUE = "translation_requests"
# STATUS_QUEUE is no longer needed for direct publishing from update_translation_status
# STATUS_QUEUE = "translation_status"

# Status tracker (in-memory dictionary removed, now using DB)
# translation_tasks = {}


class TaskStatus(Enum):
    """Enum for task status values"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_FOUND = "not_found"  # Added for consistency


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
        # Add heartbeat for better connection stability
        heartbeat=600,
        blocked_connection_timeout=300,
    )


def get_rabbitmq_client():
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

    # Use loop=asyncio.get_event_loop() for compatibility if needed
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
    Submit a translation request to the queue and create a status record in DB.
    """
    try:
        # Generate a unique task ID
        # Consider using UUID for better uniqueness: import uuid; task_id = f"translation_{uuid.uuid4()}"
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S%f")
        task_id = f"translation_{timestamp_str}_{hash(source_text) % 10000}"

        # Prepare the message for the queue
        queue_message = {
            "task_id": task_id,
            "source_text": source_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "timestamp": datetime.now().isoformat(),
        }

        # Prepare initial task data for DB
        task_db_data = {
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
            "created_at": queue_message["timestamp"],
            "source_lang": source_lang,
            "target_lang": target_lang,
            # Avoid storing large source_text in status record if it's a file reference
            "source_ref": source_text if source_text.startswith("file://") else None,
            "result": None,
            "updated_at": queue_message["timestamp"],
        }

        # Create task status record in DB *before* publishing
        db_result = await create_task_status(task_db_data)
        if not db_result.get("success"):
            logger.error(
                f"Failed to create task status in DB for {task_id}: {db_result.get('message')}"
            )
            # Decide if we should proceed or return error
            return {
                "error": db_result.get("error", "DB Error"),
                "message": "Failed to create task status record",
            }

        # Get a connection and channel
        # Use try-with-resources for connection handling
        connection = None
        try:
            connection = get_rabbitmq_client()
            channel = connection.channel()

            # Ensure translation queue exists
            ensure_queue_exists(channel, TRANSLATION_QUEUE)
            # No longer need to ensure STATUS_QUEUE here

            # Publish translation request
            channel.basic_publish(
                exchange="",
                routing_key=TRANSLATION_QUEUE,
                body=json.dumps(queue_message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    priority=priority,
                ),
            )

            logger.info(f"Translation request submitted for task_id: {task_id}")

            return {
                "task_id": task_id,
                "status": TaskStatus.PENDING.value,
                "message": "Translation request submitted successfully",
            }
        except Exception as mq_e:
            logger.error(
                f"Error publishing translation request for {task_id} to RabbitMQ: {str(mq_e)}"
            )
            # Consider compensating action: update DB status to FAILED?
            await update_task_status(
                task_id,
                TaskStatus.FAILED.value,
                result_data=f"MQ Publishing Error: {str(mq_e)}",
            )
            return {
                "error": str(mq_e),
                "message": "Failed to publish translation request to queue",
            }
        finally:
            if connection and connection.is_open:
                connection.close()

    except Exception as e:
        logger.error(f"General error submitting translation request: {str(e)}")
        # Log the full traceback if possible
        import traceback

        logger.error(traceback.format_exc())
        return {"error": str(e), "message": "Failed to submit translation request"}


# Modified to use DB function
async def get_translation_status(task_id: str) -> dict:
    """
    Get the status of a translation task from the database.
    """
    status_data = await get_task_status(task_id)
    # Ensure the returned structure matches expectations (e.g., includes task_id)
    if isinstance(status_data, dict) and "task_id" not in status_data:
        status_data["task_id"] = task_id  # Add task_id if missing from DB response
    return status_data


# Modified to use DB function
async def get_all_translation_statuses() -> list:
    """
    Get the status of all translation tasks from the database.
    """
    # Assuming get_all_task_statuses returns a dict like {"success": True, "tasks": [...]}
    result = await get_all_task_statuses(limit=1000)  # Adjust limit as needed
    if result.get("success"):
        return result.get("tasks", [])
    else:
        logger.error(
            f"Failed to get all task statuses from DB: {result.get('message')}"
        )
        return []


# Modified to use DB function - No longer publishes to RabbitMQ status queue
async def update_translation_status_in_db(
    task_id: str, status: str, result: str = None
) -> dict:
    """
    Update the status of a translation task in the database.
    This is primarily called by the worker.
    """
    # Use the DB function directly
    update_result = await update_task_status(task_id, status, result_data=result)

    if (
        isinstance(update_result, dict)
        and update_result.get("status") == TaskStatus.NOT_FOUND.value
    ):
        logger.warning(f"Task {task_id} not found in DB during status update.")
        return {
            "task_id": task_id,
            "status": TaskStatus.NOT_FOUND.value,
            "message": "Translation task not found in DB",
        }
    elif isinstance(update_result, dict) and update_result.get("success") is False:
        logger.error(
            f"Failed to update task status in DB for {task_id}: {update_result.get('message')}"
        )
        # Return an error structure
        return {
            "task_id": task_id,
            "status": "update_failed",  # Indicate DB update failure
            "error": update_result.get("error", "DB Update Error"),
            "message": f"Failed to update task status in DB: {update_result.get('message')}",
        }
    else:
        # Return the updated document (which is the result of update_task_status on success)
        logger.info(f"Task {task_id} status updated to {status} in DB.")
        return update_result


# Modified worker to use DB functions and save history
async def start_translation_worker(translate_function) -> None:
    """
    Start a worker to process translation requests one at a time, using DB for status.
    """
    while True:  # Keep trying to connect and consume
        connection = None
        try:
            connection = get_rabbitmq_client()
            channel = connection.channel()
            ensure_queue_exists(channel, TRANSLATION_QUEUE)
            channel.basic_qos(prefetch_count=1)

            logger.info("Translation worker connected. Waiting for messages...")

            for method_frame, properties, body in channel.consume(
                TRANSLATION_QUEUE, inactivity_timeout=1
            ):
                # Check if connection is still open, otherwise break to reconnect
                if not connection or connection.is_closed:
                    logger.warning(
                        "RabbitMQ connection closed, attempting to reconnect..."
                    )
                    break
                # If no message, continue loop (inactivity_timeout)
                if method_frame is None:
                    continue

                task_id = None  # Initialize task_id
                try:
                    message = json.loads(body)
                    task_id = message.get("task_id")
                    source_text = message.get("source_text")
                    source_lang = message.get("source_lang", "auto")
                    target_lang = message.get("target_lang", "en")

                    if not task_id or not source_text:
                        logger.error(f"Invalid message received: {body.decode()}")
                        channel.basic_reject(
                            delivery_tag=method_frame.delivery_tag, requeue=False
                        )  # Don't requeue bad messages
                        continue

                    logger.info(f"Processing translation task {task_id}")

                    # Update status to PROCESSING in DB
                    await update_translation_status_in_db(
                        task_id, TaskStatus.PROCESSING.value
                    )

                    # Perform the translation
                    translated_text = None
                    translation_error = None
                    try:
                        translated_text = await translate_function(
                            source_text=source_text,
                            source_lang=source_lang,
                            target_lang=target_lang,
                        )
                        # Update status to COMPLETED in DB
                        await update_translation_status_in_db(
                            task_id, TaskStatus.COMPLETED.value, result=translated_text
                        )
                        # Save to history collection
                        await save_translation_result(
                            task_id,
                            source_text,
                            source_lang,
                            target_lang,
                            translated_text,
                        )
                        logger.info(f"Task {task_id} completed successfully.")

                    except Exception as translate_e:
                        logger.error(
                            f"Translation error for task {task_id}: {str(translate_e)}"
                        )
                        translation_error = f"Translation error: {str(translate_e)}"
                        # Update status to FAILED in DB
                        await update_translation_status_in_db(
                            task_id, TaskStatus.FAILED.value, result=translation_error
                        )
                        # Save failure to history collection
                        await save_translation_result(
                            task_id,
                            source_text,
                            source_lang,
                            target_lang,
                            translation_error,
                        )
                        logger.info(f"Task {task_id} failed.")

                    # Acknowledge the message
                    channel.basic_ack(delivery_tag=method_frame.delivery_tag)

                except json.JSONDecodeError as json_e:
                    logger.error(
                        f"Failed to decode JSON message: {body.decode()} - Error: {json_e}"
                    )
                    channel.basic_reject(
                        delivery_tag=method_frame.delivery_tag, requeue=False
                    )  # Reject malformed JSON
                except Exception as process_e:
                    logger.error(
                        f"Error processing message for task {task_id or 'unknown'}: {str(process_e)}"
                    )
                    import traceback

                    logger.error(traceback.format_exc())
                    # Try to update status to FAILED if task_id is known
                    if task_id:
                        try:
                            await update_translation_status_in_db(
                                task_id,
                                TaskStatus.FAILED.value,
                                result=f"Worker processing error: {str(process_e)}",
                            )
                            # Also save failure to history
                            await save_translation_result(
                                task_id,
                                message.get("source_text", "N/A"),
                                message.get("source_lang", "N/A"),
                                message.get("target_lang", "N/A"),
                                f"Worker processing error: {str(process_e)}",
                            )
                        except Exception as db_update_e:
                            logger.error(
                                f"Failed to update DB status to FAILED for task {task_id} after processing error: {db_update_e}"
                            )

                    # Reject the message but decide whether to requeue based on the error type
                    # For now, let's not requeue to avoid potential infinite loops on persistent errors
                    channel.basic_reject(
                        delivery_tag=method_frame.delivery_tag, requeue=False
                    )

            # If consume loop finishes (e.g., connection closed), close channel and connection
            if channel and channel.is_open:
                channel.close()
            if connection and connection.is_open:
                connection.close()
            logger.info("Worker consume loop finished or connection lost.")

        except pika.exceptions.AMQPConnectionError as conn_err:
            logger.error(
                f"Worker connection error: {conn_err}. Retrying in 10 seconds..."
            )
        except Exception as e:
            logger.error(
                f"Unexpected worker error: {str(e)}. Retrying in 10 seconds..."
            )
            import traceback

            logger.error(traceback.format_exc())
        finally:
            # Ensure connection is closed if it exists and is open
            if connection and connection.is_open:
                try:
                    connection.close()
                except Exception as close_e:
                    logger.error(f"Error closing RabbitMQ connection: {close_e}")
            # Wait before attempting to reconnect
            await asyncio.sleep(10)


# Example translation function remains the same
async def example_translate_function(
    source_text: str, source_lang: str, target_lang: str
) -> str:
    """
    Example translation function. Replace with actual translation implementation.
    """
    await asyncio.sleep(2)
    return f"Translated from {source_lang} to {target_lang}: {source_text}"


# Modified initialization function
async def initialize_translation_service(translate_function=None):
    """
    Initialize the translation service and start the worker using DB persistence.
    """
    if translate_function is None:
        try:
            from main import custom_translate_function

            translate_function = custom_translate_function
            logger.info("Using custom_translate_function from main.py for worker.")
        except ImportError:
            logger.warning(
                "custom_translate_function not found in main.py, using example_translate_function."
            )
            translate_function = example_translate_function

    # Start the worker in a separate task
    # The worker now runs in a continuous loop with reconnection logic
    asyncio.create_task(start_translation_worker(translate_function))

    logger.info("Translation service initialized (worker started)")
    return {
        "status": "initialized",
        "message": "Translation service worker started successfully",
    }
