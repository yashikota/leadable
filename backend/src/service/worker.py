import os
import asyncio

from discord_webhook import DiscordWebhook
from pydantic import BaseModel

from service.db import TaskStatus, update_task_status
from service.log import logger
from service.mq import celery_app, publish_task_update
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


@celery_app.task(name="worker.process_translation_task")
def process_translation_task(task_data):
    task = TranslationTask(**task_data)

    try:
        update_task_status_sync(task.task_id, TaskStatus.PROCESSING.value)
        publish_task_update_sync(task.task_id, TaskStatus.PROCESSING.value)

        logger.info(
            f"Processing translation task {task.task_id} for file {task.filename}"
        )

        try:
            original_pdf_data = download_file_sync(f"uploads/{task.filename}")
            logger.info(f"Downloaded PDF data for task {task.task_id}")
        except Exception as e:
            error_msg = f"Failed to download PDF data: {str(e)}"
            logger.error(f"{error_msg} for task {task.task_id}")
            update_task_status_sync(task.task_id, TaskStatus.FAILED.value)
            publish_task_update_sync(task.task_id, TaskStatus.FAILED.value, error_msg)
            return False

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

        is_success, result_data = pdf_translate_sync(ts)

        if not is_success:
            logger.error(f"Translation failed for task {task.task_id}: {result_data}")
            update_task_status_sync(task.task_id, TaskStatus.FAILED.value)
            publish_task_update_sync(
                task.task_id,
                TaskStatus.FAILED.value,
                f"Translation failed: {result_data}",
            )
            return False

        upload_key = f"translated/{task.filename}"
        is_upload_success = upload_file_sync(result_data, upload_key, task.content_type)

        if not is_upload_success:
            logger.error(f"Failed to upload translated file for task {task.task_id}")
            update_task_status_sync(task.task_id, TaskStatus.FAILED.value)
            publish_task_update_sync(
                task.task_id,
                TaskStatus.FAILED.value,
                "Failed to upload translated file",
            )
            return False

        update_task_status_sync(task.task_id, TaskStatus.COMPLETED.value)
        publish_task_update_sync(task.task_id, TaskStatus.COMPLETED.value)

        logger.info(f"Translation completed successfully for task {task.task_id}")

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
        update_task_status_sync(task.task_id, TaskStatus.FAILED.value)
        publish_task_update_sync(
            task.task_id, TaskStatus.FAILED.value, f"Error: {str(e)}"
        )
        return False


def update_task_status_sync(task_id, status):
    return asyncio.run(update_task_status(task_id, status))


def publish_task_update_sync(task_id, status, message=None):
    return asyncio.run(publish_task_update(task_id, status, message))


def download_file_sync(path):
    return asyncio.run(download_file(path))


def upload_file_sync(data, path, content_type):
    return asyncio.run(upload_file(data, path, content_type))


def pdf_translate_sync(ts):
    return asyncio.run(ts.pdf_translate())
