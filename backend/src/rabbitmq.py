import aio_pika
import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"

async def get_connection():
    return await aio_pika.connect_robust(RABBITMQ_URL)

async def publish_message(queue_name: str, message: Dict[str, Any]):
    connection = await get_connection()
    async with connection:
        channel = await connection.channel()
        await channel.declare_queue(queue_name, durable=True)

        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=queue_name
        )

async def process_translation_queue():
    from translate import pdf_translate  # Import here to avoid circular imports

    connection = await get_connection()
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue("translation_queue", durable=True)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        body = json.loads(message.body.decode())
                        input_pdf_data = body["pdf_data"]
                        filename = body["filename"]

                        result_pdf = await pdf_translate(input_pdf_data)

                        if result_pdf:
                            # Publish result to completion queue
                            await publish_message("translation_complete", {
                                "filename": filename,
                                "success": True
                            })
                        else:
                            await publish_message("translation_complete", {
                                "filename": filename,
                                "success": False,
                                "error": "Translation failed"
                            })
                    except Exception as e:
                        logger.error(f"Error processing translation: {str(e)}")
                        await publish_message("translation_complete", {
                            "filename": filename,
                            "success": False,
                            "error": str(e)
                        })
