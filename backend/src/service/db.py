import os
from datetime import datetime
from logging import getLogger

from bson.errors import InvalidId
from bson.objectid import ObjectId
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import OperationFailure

logger = getLogger(__name__)

# MongoDB configuration
MONGO_HOST = os.getenv("MONGO_HOST", "mongo")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_USERNAME = os.getenv("MONGO_INITDB_ROOT_USERNAME", "root")
MONGO_PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD", "example")
MONGO_DB = os.getenv("MONGO_DB", "leadable")
MONGO_COLLECTION_COMPLETED = os.getenv("MONGO_COLLECTION_COMPLETED", "completed_tasks")
MONGO_COLLECTION_TASKS = os.getenv(
    "MONGO_COLLECTION_TASKS", "tasks"
)  # New collection for task status


def get_mongo_client():
    """
    Initialize and return a MongoDB client.
    """
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


# ==================== Task Status Functions ====================


async def create_task_status(task_data):
    """
    Create a new task status record in the database.

    Args:
        task_data: Dictionary containing initial task data (must include task_id)

    Returns:
        Dictionary with saved document information or error
    """
    try:
        if "task_id" not in task_data:
            raise ValueError("task_id is required to create a task status record")

        collection = get_collection(MONGO_COLLECTION_TASKS)
        # Use update_one with upsert=True to avoid race conditions if called multiple times
        result = collection.update_one(
            {"task_id": task_data["task_id"]},
            {
                "$set": task_data,
                "$setOnInsert": {"created_at": datetime.now().isoformat()},
            },
            upsert=True,
        )

        if result.upserted_id:
            return {
                "success": True,
                "document_id": str(result.upserted_id),
                "message": "Task status created successfully",
            }
        elif result.matched_count > 0:
            return {
                "success": True,
                "message": "Task status already existed, updated.",  # Or just return success
            }
        else:
            return {
                "success": False,
                "message": "Failed to create or update task status",
            }

    except Exception as e:
        logger.error(
            f"Error creating task status for {task_data.get('task_id')}: {str(e)}"
        )
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to create task status",
        }


async def update_task_status(
    task_id: str, status: str, result_data: str = None, updated_at: str = None
):
    """
    Update the status and optionally the result of a task.

    Args:
        task_id: ID of the task to update
        status: New status string
        result_data: Optional result data (e.g., translated text or error message)
        updated_at: Optional timestamp for the update

    Returns:
        Dictionary with updated task data or error information
    """
    try:
        collection = get_collection(MONGO_COLLECTION_TASKS)
        update_fields = {
            "status": status,
            "updated_at": updated_at or datetime.now().isoformat(),
        }
        if result_data is not None:
            update_fields["result"] = result_data

        updated_document = collection.find_one_and_update(
            {"task_id": task_id},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,  # Return the updated document
        )

        if updated_document:
            return _convert_objectid_to_str(updated_document)
        else:
            logger.warning(f"Attempted to update non-existent task {task_id}")
            return {
                "success": False,
                "message": f"Task with id {task_id} not found for update",
            }
    except Exception as e:
        logger.error(f"Error updating task status for {task_id}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to update task status for {task_id}",
        }


async def get_task_status(task_id: str):
    """
    Retrieve a task status record by its task_id.

    Args:
        task_id: ID of the task to retrieve

    Returns:
        Dictionary containing the task data or error information
    """
    try:
        collection = get_collection(MONGO_COLLECTION_TASKS)
        document = collection.find_one({"task_id": task_id})

        if document:
            return _convert_objectid_to_str(document)
        else:
            # Return a specific structure indicating not found, consistent with mq.py logic
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": "Translation task not found in DB",
            }
    except Exception as e:
        logger.error(f"Error retrieving task status for {task_id}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve task status {task_id}",
        }


async def get_all_task_statuses(
    limit=100, skip=0, sort_field="created_at", sort_order=-1
):
    """
    List task statuses with pagination and sorting.

    Args:
        limit: Maximum number of tasks to return
        skip: Number of tasks to skip (for pagination)
        sort_field: Field to sort by
        sort_order: Sort order (1 for ascending, -1 for descending)

    Returns:
        Dictionary with list of tasks and pagination information
    """
    try:
        collection = get_collection(MONGO_COLLECTION_TASKS)
        query = {}

        total_count = collection.count_documents(query)

        cursor = collection.find(query)
        cursor = cursor.sort(sort_field, sort_order)
        cursor = cursor.skip(skip).limit(limit)

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
        logger.error(f"Error listing task statuses: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to list task statuses",
        }


# ==================== Completed Task Functions (History) ====================


async def save_completed_task(task_data):
    """
    Save a completed task to the history collection.
    This is separate from the main task status tracking.

    Args:
        task_data: Dictionary containing task data
    Returns:
        Dictionary with saved document information
    """
    try:
        if "completed_at" not in task_data:
            task_data["completed_at"] = datetime.now().isoformat()

        collection = get_collection(MONGO_COLLECTION_COMPLETED)
        result = collection.insert_one(task_data)

        return {
            "success": True,
            "document_id": str(result.inserted_id),
            "message": "Completed task saved to history successfully",
        }
    except Exception as e:
        logger.error(f"Error saving completed task to history: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to save completed task to history",
        }


async def get_completed_task(task_id):
    """
    Retrieve a completed task from history by its ID.
    """
    try:
        collection = get_collection(MONGO_COLLECTION_COMPLETED)
        try:
            document = collection.find_one({"_id": ObjectId(task_id)})
        except InvalidId:
            document = collection.find_one({"task_id": task_id})

        if document:
            return _convert_objectid_to_str(document)
        else:
            return {
                "success": False,
                "message": f"Completed task with id {task_id} not found in history",
            }
    except Exception as e:
        logger.error(
            f"Error retrieving completed task {task_id} from history: {str(e)}"
        )
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve completed task {task_id} from history",
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
    List completed tasks from history with pagination, sorting and filtering.
    """
    try:
        collection = get_collection(MONGO_COLLECTION_COMPLETED)
        query = {}
        if task_type:
            query["task_type"] = task_type
        if search_text:
            query["$or"] = [
                {"source_text": {"$regex": search_text, "$options": "i"}},
                {"result": {"$regex": search_text, "$options": "i"}},
                {"task_id": {"$regex": search_text, "$options": "i"}},
            ]

        total_count = collection.count_documents(query)
        cursor = collection.find(query)
        cursor = cursor.sort(sort_field, sort_order)
        cursor = cursor.skip(skip).limit(limit)
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
        logger.error(f"Error listing completed tasks from history: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to list completed tasks from history",
        }


async def delete_completed_task(task_id):
    """
    Delete a completed task from history by its ID.
    """
    try:
        collection = get_collection(MONGO_COLLECTION_COMPLETED)
        try:
            result = collection.delete_one({"_id": ObjectId(task_id)})
        except InvalidId:
            result = collection.delete_one({"task_id": task_id})

        if result.deleted_count > 0:
            return {
                "success": True,
                "message": f"Completed task {task_id} deleted from history successfully",
            }
        else:
            return {
                "success": False,
                "message": f"Completed task {task_id} not found in history",
            }
    except Exception as e:
        logger.error(f"Error deleting completed task {task_id} from history: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to delete completed task {task_id} from history",
        }


async def save_translation_result(
    task_id, source_text, source_lang, target_lang, result
):
    """
    Save a completed translation task to the history database.
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
    """
    return await get_completed_tasks(
        limit=limit,
        skip=skip,
        sort_field="completed_at",
        sort_order=-1,
        task_type="translation",
        search_text=search_text,
    )


# ==================== Initialization ====================


def create_indexes():
    """
    Create indexes for better query performance for all relevant collections.
    """
    try:
        # Indexes for Completed Tasks (History)
        completed_collection = get_collection(MONGO_COLLECTION_COMPLETED)
        completed_collection.create_index(
            "task_id", unique=False
        )  # Allow multiple history entries? Or should task_id be unique here too? Assuming not unique for now.
        completed_collection.create_index([("task_type", 1), ("completed_at", -1)])

        # Check existing indexes before creating text search index to avoid conflicts
        existing_indexes = list(completed_collection.list_indexes())
        text_index_exists = any(
            idx.get("name", "").endswith("_text")
            and "weights" in idx
            and all(
                field in idx["weights"]
                for field in ["source_text", "result", "task_id"]
            )
            for idx in existing_indexes
        )

        if not text_index_exists:
            # Only create if no text index exists on these fields
            completed_collection.create_index(
                [("source_text", "text"), ("result", "text"), ("task_id", "text")],
                name="completed_text_search_idx",
            )
            logger.info("Created text search index for completed tasks")
        else:
            logger.info(
                "Text search index already exists for completed tasks, skipping creation"
            )

        logger.info(f"Indexes created for collection: {MONGO_COLLECTION_COMPLETED}")

        # Indexes for Task Status Tracking
        tasks_collection = get_collection(MONGO_COLLECTION_TASKS)
        tasks_collection.create_index(
            "task_id", unique=True
        )  # task_id MUST be unique here
        tasks_collection.create_index([("status", 1), ("created_at", -1)])
        tasks_collection.create_index("created_at")
        logger.info(f"Indexes created for collection: {MONGO_COLLECTION_TASKS}")

    except OperationFailure as e:
        if e.code == 85:  # IndexOptionsConflict
            logger.warning(
                f"Index conflict during creation: {str(e)}, full error: {e.details}"
            )
        else:
            logger.error(
                f"Error creating indexes (OperationFailure): {str(e)}, full error: {e.details}"
            )
    except Exception as e:
        # Catch other potential errors during index creation
        logger.error(f"Unexpected error creating indexes: {str(e)}")
        # Don't raise here, allow app to potentially continue


def initialize_database():
    """
    Initialize the database and create necessary collections and indexes.
    """
    try:
        db = get_database()

        # Ensure Completed Tasks collection exists
        if MONGO_COLLECTION_COMPLETED not in db.list_collection_names():
            db.create_collection(MONGO_COLLECTION_COMPLETED)
            logger.info(f"Created collection: {MONGO_COLLECTION_COMPLETED}")

        # Ensure Task Status collection exists
        if MONGO_COLLECTION_TASKS not in db.list_collection_names():
            db.create_collection(MONGO_COLLECTION_TASKS)
            logger.info(f"Created collection: {MONGO_COLLECTION_TASKS}")

        # Create/Update indexes (safe to run multiple times)
        create_indexes()

        # Test connection
        client = get_mongo_client()
        client.admin.command("ping")  # Check connection after setup
        logger.info("Database connection successful.")

        return {"status": "initialized", "message": "Database initialized successfully"}
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
