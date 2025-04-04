import os
from enum import Enum

from pymongo import MongoClient
from pymongo.errors import OperationFailure

from service.log import logger

# MongoDB configuration
MONGO_HOST = os.getenv("MONGO_HOST", "mongo")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_USERNAME = os.getenv("MONGO_INITDB_ROOT_USERNAME", "root")
MONGO_PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD", "example")
MONGO_DB = os.getenv("MONGO_DB", "leadable")
MONGO_COLLECTION_TASKS = "tasks"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def get_mongo_client():
    try:
        connection_string = (
            f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/"
        )
        # Increase timeout settings
        return MongoClient(
            connection_string,
            serverSelectionTimeoutMS=30000,  # 30 seconds
            connectTimeoutMS=30000,  # 30 seconds
            socketTimeoutMS=30000,  # 30 seconds
        )
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise


def get_database(database_name=MONGO_DB):
    client = get_mongo_client()
    return client[database_name]


def get_collection(collection_name, database_name=MONGO_DB):
    db = get_database(database_name)
    return db[collection_name]


async def update_task_status(task_id: str, status: str):
    try:
        tasks_collection = get_collection(MONGO_COLLECTION_TASKS)
        result = tasks_collection.update_one(
            {"task_id": task_id}, {"$set": {"status": status}}
        )

        if result.matched_count == 0:
            logger.warning(f"Task {task_id} not found when updating status to {status}")
            return False

        logger.info(f"Updated task {task_id} status to {status}")
        return True
    except Exception as e:
        logger.error(f"Error updating task status for {task_id}: {str(e)}")
        return False


async def store_result(task_data: dict) -> bool:
    try:
        tasks_collection = get_collection(MONGO_COLLECTION_TASKS)
        tasks_collection.insert_one(task_data)
        return True
    except Exception as e:
        logger.error(f"Error storing result: {str(e)}")
        return False


async def get_all_tasks():
    try:
        tasks_collection = get_collection(MONGO_COLLECTION_TASKS)
        cursor = tasks_collection.find({})
        results = []
        for doc in cursor:
            if "_id" in doc and hasattr(doc["_id"], "__str__"):
                doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results
    except Exception as e:
        logger.error(f"Error fetching all results: {str(e)}")
        raise


async def get_task(task_id: str):
    try:
        tasks_collection = get_collection(MONGO_COLLECTION_TASKS)
        result = tasks_collection.find_one({"task_id": task_id})
        if not result:
            return {"error": "Task not found"}
        if "_id" in result and hasattr(result["_id"], "__str__"):
            result["_id"] = str(result["_id"])
        return result
    except Exception as e:
        logger.error(f"Error fetching result {task_id}: {str(e)}")
        raise


async def delete_task(task_id: str):
    try:
        tasks_collection = get_collection(MONGO_COLLECTION_TASKS)
        result = tasks_collection.delete_one({"task_id": task_id})
        if result.deleted_count == 0:
            return {"error": "Task not found"}
        return {"status": "deleted", "task_id": task_id}
    except Exception as e:
        logger.error(f"Error deleting result {task_id}: {str(e)}")
        raise


def create_indexes():
    try:
        tasks_collection = get_collection(MONGO_COLLECTION_TASKS)
        tasks_collection.create_index("task_id", unique=True)
        tasks_collection.create_index("created_at")
        logger.info(f"Indexes created for collection: {MONGO_COLLECTION_TASKS}")
    except OperationFailure as e:
        logger.error(
            f"Error creating indexes (OperationFailure): {str(e)}, full error: {e.details}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating indexes: {str(e)}")


def initialize_database() -> bool:
    try:
        db = get_database()

        # Ensure Task Status collection exists
        if MONGO_COLLECTION_TASKS not in db.list_collection_names():
            db.create_collection(MONGO_COLLECTION_TASKS)
            logger.info(f"Created collection: {MONGO_COLLECTION_TASKS}")

        create_indexes()

        # Test connection
        client = get_mongo_client()
        client.admin.command("ping")
        logger.info("Database connection successful.")
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        return False
