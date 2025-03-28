import asyncio
import json
import os
import signal
import sys

from discord_webhook import DiscordWebhook
from pydantic import BaseModel

from service.db import TaskStatus, update_task_status
from service.log import logger
from service.mq import TRANSLATION_QUEUE, get_rabbitmq_client, publish_task_update
from service.storage import download_file, upload_file
from service.translate import TranslationService


class TranslationTask(BaseModel):
    task_id: str
    filename: str
    content_type: str
    original_url: str
    translated_url: str
    source_lang: str
    target_lang: str
    provider: str = None
    model_name: str = None
    api_key: str = None


async def process_translation_task(task_data):
    task = TranslationTask(**task_data)

    try:
        # Update task status to processing
        await update_task_status(task.task_id, TaskStatus.PROCESSING.value)
        await publish_task_update(task.task_id, TaskStatus.PROCESSING.value)

        logger.info(
            f"Processing translation task {task.task_id} for file {task.filename}"
        )

        # Download the PDF data from storage
        try:
            original_pdf_data = await download_file(f"uploads/{task.filename}")
            logger.info(f"Downloaded PDF data for task {task.task_id}")
        except Exception as e:
            error_msg = f"Failed to download PDF data: {str(e)}"
            logger.error(f"{error_msg} for task {task.task_id}")
            await update_task_status(task.task_id, TaskStatus.FAILED.value)
            await publish_task_update(task.task_id, TaskStatus.FAILED.value, error_msg)
            return False

        # Create translation service
        ts = TranslationService()
        ts.task_id = task.task_id
        ts.status = TaskStatus.PROCESSING
        ts.original_pdf_data = original_pdf_data
        ts.filename = task.filename
        ts.content_type = task.content_type
        ts.original_url = task.original_url
        ts.translated_url = task.translated_url
        ts.source_lang = task.source_lang
        ts.target_lang = task.target_lang
        ts.provider = task.provider
        ts.model_name = task.model_name
        ts.api_key = task.api_key

        # Perform the translation
        is_success, result_data = await ts.pdf_translate()

        if not is_success:
            logger.error(f"Translation failed for task {task.task_id}: {result_data}")
            await update_task_status(task.task_id, TaskStatus.FAILED.value)
            await publish_task_update(
                task.task_id,
                TaskStatus.FAILED.value,
                f"Translation failed: {result_data}",
            )
            return False

        # Upload the translated file
        upload_key = f"translated/{task.filename}"
        is_upload_success = await upload_file(
            result_data, upload_key, task.content_type
        )

        if not is_upload_success:
            logger.error(f"Failed to upload translated file for task {task.task_id}")
            await update_task_status(task.task_id, TaskStatus.FAILED.value)
            await publish_task_update(
                task.task_id,
                TaskStatus.FAILED.value,
                "Failed to upload translated file",
            )
            return False

        # Update task status to completed
        await update_task_status(task.task_id, TaskStatus.COMPLETED.value)
        await publish_task_update(task.task_id, TaskStatus.COMPLETED.value)

        logger.info(f"Translation completed successfully for task {task.task_id}")

        # Send Discord notification
        if webhook_url := os.getenv("DISCORD_WEBHOOK_URL"):
            try:
                webhook = DiscordWebhook(
                    url=webhook_url,
                    content=f"翻訳が完了しました！[{task.filename}]({task.translated_url})",
                )
                webhook.execute()
                logger.info(
                    f"Discord notification sent for completed task {task.task_id}"
                )
            except Exception as e:
                logger.error(f"Failed to send Discord notification: {str(e)}")

        return True

    except Exception as e:
        logger.error(f"Error processing translation task {task.task_id}: {str(e)}")
        await update_task_status(task.task_id, TaskStatus.FAILED.value)
        await publish_task_update(
            task.task_id, TaskStatus.FAILED.value, f"Error: {str(e)}"
        )
        return False


def callback(ch, method, properties, body):
    """
    Callback function for RabbitMQ message processing.
    """
    try:
        task_data = json.loads(body)
        logger.info(f"Received task: {task_data.get('task_id')}")

        # Process the translation task
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(process_translation_task(task_data))

        if result:
            logger.info(f"Task {task_data.get('task_id')} processed successfully")
        else:
            logger.error(f"Task {task_data.get('task_id')} processing failed")

    except Exception as e:
        logger.error(f"Error in task callback: {str(e)}")
    finally:
        # Acknowledge the message to remove it from the queue
        ch.basic_ack(delivery_tag=method.delivery_tag)


def start_worker():
    logger.info("Starting translation worker...")
    try:
        # Set up RabbitMQ connection
        connection = get_rabbitmq_client()
        channel = connection.channel()

        # Declare the queue
        channel.queue_declare(queue=TRANSLATION_QUEUE, durable=True)

        # Don't give more than one message to a worker at a time
        channel.basic_qos(prefetch_count=1)

        # Set up the consumer
        channel.basic_consume(queue=TRANSLATION_QUEUE, on_message_callback=callback)

        logger.info("Worker started, waiting for messages...")
        channel.start_consuming()

    except KeyboardInterrupt:
        logger.info("Worker stopping...")
        if "channel" in locals() and channel:
            channel.stop_consuming()
        if "connection" in locals() and connection:
            connection.close()
        logger.info("Worker stopped")
    except Exception as e:
        logger.error(f"Worker error: {str(e)}")
        sys.exit(1)


def handle_signal(sig, frame):
    """Handle signals to gracefully shutdown the worker."""
    logger.info(f"Received signal {sig}, shutting down worker...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    start_worker()
