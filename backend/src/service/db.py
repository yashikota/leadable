import logging
import os
from datetime import datetime

from bson.errors import InvalidId
from bson.objectid import ObjectId
from pymongo import MongoClient

# MongoDB configuration
MONGO_HOST = os.getenv("MONGO_HOST", "db")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_USERNAME = os.getenv("MONGO_INITDB_ROOT_USERNAME", "root")
MONGO_PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
MONGO_DB = os.getenv("MONGO_DB", "leadable")
MONGO_COLLECTION_COMPLETED = os.getenv("MONGO_COLLECTION_COMPLETED", "completed_tasks")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_mongo_client():
    """
    Initialize and return a MongoDB client.
    """
    try:
        connection_string = (
            f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/"
        )
        return MongoClient(connection_string)
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise


def get_database(database_name=MONGO_DB):
    """
    Get the specified database.
    """
    client = get_mongo_client()
    return client[database_name]


def get_collection(collection_name, database_name=MONGO_DB):
    """
    Get the specified collection from the database.
    """
    db = get_database(database_name)
    return db[collection_name]


def _convert_objectid_to_str(document):
    """
    Convert MongoDB ObjectId to string for JSON serialization.
    """
    if document and "_id" in document and isinstance(document["_id"], ObjectId):
        document["_id"] = str(document["_id"])
    return document


async def save_completed_task(task_data):
    """
    Save a completed task to the database.

    Args:
        task_data: Dictionary containing task data

    Returns:
        Dictionary with saved document information
    """
    try:
        # Add timestamp if not present
        if "completed_at" not in task_data:
            task_data["completed_at"] = datetime.now().isoformat()

        collection = get_collection(MONGO_COLLECTION_COMPLETED)
        result = collection.insert_one(task_data)

        return {
            "success": True,
            "document_id": str(result.inserted_id),
            "message": "Task saved successfully",
        }
    except Exception as e:
        logger.error(f"Error saving completed task: {str(e)}")
        return {"success": False, "error": str(e), "message": "Failed to save task"}


async def get_completed_task(task_id):
    """
    Retrieve a completed task by its ID.

    Args:
        task_id: ID of the task to retrieve

    Returns:
        Dictionary containing the task data or error information
    """
    try:
        collection = get_collection(MONGO_COLLECTION_COMPLETED)

        # First try to find by the MongoDB _id
        try:
            document = collection.find_one({"_id": ObjectId(task_id)})
        except InvalidId:
            # If not a valid ObjectId, try to find by task_id field
            document = collection.find_one({"task_id": task_id})

        if document:
            return _convert_objectid_to_str(document)
        else:
            return {"success": False, "message": f"Task with id {task_id} not found"}
    except Exception as e:
        logger.error(f"Error retrieving task {task_id}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve task {task_id}",
        }


async def get_completed_tasks(
    limit=50,
    skip=0,
    sort_field="completed_at",
    sort_order=-1,
    task_type=None,
    search_text=None,
):
    """
    List completed tasks with pagination, sorting and filtering.

    Args:
        limit: Maximum number of tasks to return
        skip: Number of tasks to skip (for pagination)
        sort_field: Field to sort by
        sort_order: Sort order (1 for ascending, -1 for descending)
        task_type: Optional filter by task type
        search_text: Optional text search in task content

    Returns:
        Dictionary with list of tasks and pagination information
    """
    try:
        collection = get_collection(MONGO_COLLECTION_COMPLETED)

        # Build the query
        query = {}
        if task_type:
            query["task_type"] = task_type

        if search_text:
            # Text search across multiple fields
            query["$or"] = [
                {"source_text": {"$regex": search_text, "$options": "i"}},
                {"result": {"$regex": search_text, "$options": "i"}},
                {"task_id": {"$regex": search_text, "$options": "i"}},
            ]

        # Get total count for pagination
        total_count = collection.count_documents(query)

        # Get the tasks with pagination and sorting
        cursor = collection.find(query)
        cursor = cursor.sort(sort_field, sort_order)
        cursor = cursor.skip(skip).limit(limit)

        # Convert ObjectIds to strings for JSON serialization
        tasks = [_convert_objectid_to_str(doc) for doc in cursor]

        return {
            "success": True,
            "tasks": tasks,
            "total": total_count,
            "page": skip // limit + 1 if limit > 0 else 1,
            "limit": limit,
            "pages": (total_count + limit - 1) // limit if limit > 0 else 1,
        }
    except Exception as e:
        logger.error(f"Error listing completed tasks: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to list completed tasks",
        }


async def delete_completed_task(task_id):
    """
    Delete a completed task by its ID.

    Args:
        task_id: ID of the task to delete

    Returns:
        Dictionary with deletion status
    """
    try:
        collection = get_collection(MONGO_COLLECTION_COMPLETED)

        # Try both the MongoDB _id and task_id field
        try:
            result = collection.delete_one({"_id": ObjectId(task_id)})
        except InvalidId:
            result = collection.delete_one({"task_id": task_id})

        if result.deleted_count > 0:
            return {"success": True, "message": f"Task {task_id} deleted successfully"}
        else:
            return {"success": False, "message": f"Task {task_id} not found"}
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to delete task {task_id}",
        }


async def save_translation_result(
    task_id, source_text, source_lang, target_lang, result
):
    """
    Save a completed translation task to the database.

    Args:
        task_id: ID of the translation task
        source_text: Original text
        source_lang: Source language
        target_lang: Target language
        result: Translated text

    Returns:
        Dictionary with saved document information
    """
    task_data = {
        "task_id": task_id,
        "task_type": "translation",
        "source_text": source_text,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "result": result,
        "completed_at": datetime.now().isoformat(),
    }

    return await save_completed_task(task_data)


async def get_translation_history(limit=50, skip=0, search_text=None):
    """
    Get the translation history for displaying in the frontend.

    Args:
        limit: Maximum number of translations to return
        skip: Number of translations to skip (for pagination)
        search_text: Optional text search in translations

    Returns:
        Dictionary with list of translations and pagination information
    """
    return await get_completed_tasks(
        limit=limit,
        skip=skip,
        sort_field="completed_at",
        sort_order=-1,
        task_type="translation",
        search_text=search_text,
    )


# Create indexes for better query performance
def create_indexes():
    """
    Create indexes for better query performance.
    """
    try:
        collection = get_collection(MONGO_COLLECTION_COMPLETED)

        # Index for task_id lookups
        collection.create_index("task_id")

        # Index for task_type + timestamp for listing by type
        collection.create_index([("task_type", 1), ("completed_at", -1)])

        # Text index for text search
        collection.create_index(
            [("source_text", "text"), ("result", "text"), ("task_id", "text")]
        )

        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")


# Initialize database indexes when module is loaded
def initialize_database():
    """
    Initialize the database and create necessary collections and indexes.
    """
    try:
        # Get database and create collection if it doesn't exist
        db = get_database()
        if MONGO_COLLECTION_COMPLETED not in db.list_collection_names():
            db.create_collection(MONGO_COLLECTION_COMPLETED)
            logger.info(f"Created collection {MONGO_COLLECTION_COMPLETED}")

        # Create indexes
        create_indexes()

        return {"status": "initialized", "message": "Database initialized successfully"}
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        return {
            "status": "error",
            "message": f"Database initialization failed: {str(e)}",
        }
