import asyncio
import logging

from rabbitmq import process_translation_queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting translation worker...")
    await process_translation_queue()

if __name__ == "__main__":
    asyncio.run(main())
