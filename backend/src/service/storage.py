import json
import os
import tempfile

import minio

from service.log import logger

# MinIO client configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "root")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
DEFAULT_BUCKET = os.getenv("MINIO_DEFAULT_BUCKET", "leadable")


def get_minio_client() -> minio.Minio:
    return minio.Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def initialize_storage() -> bool:
    """
    Create the default bucket if it does not exist
    Apply bucket policy to allow public read access
    """
    try:
        client = get_minio_client()
        ensure_bucket_exists(client, DEFAULT_BUCKET)

        # Apply bucket policy to allow public read access
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{DEFAULT_BUCKET}/*"],
                }
            ],
        }
        client.set_bucket_policy(DEFAULT_BUCKET, json.dumps(policy))
        logger.info(f"Applied bucket policy to {DEFAULT_BUCKET}")
        return True
    except Exception as e:
        logger.error(f"Error initializing storage: {str(e)}")
        return False


def ensure_bucket_exists(client: minio.Minio, bucket_name: str) -> None:
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info(f"Created bucket: {bucket_name}")
    except Exception as e:
        logger.error(f"Error ensuring bucket exists: {str(e)}")
        raise


async def upload_file(file: bytes, filename: str, filetype: str) -> bool:
    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file)

        try:
            client = get_minio_client()
            ensure_bucket_exists(client, DEFAULT_BUCKET)
            client.fput_object(
                bucket_name=DEFAULT_BUCKET,
                object_name=filename,
                file_path=temp_file.name,
                content_type=filetype,
            )
            return True
        except Exception as e:
            logger.error(f"MinIO upload error: {str(e)}")
            return False
        finally:
            os.unlink(temp_file.name)
    except Exception as e:
        logger.error(f"Error writing file to disk: {str(e)}")
        return False


def get_file_url(filename: str) -> str:
    ADDRESS = os.getenv("SERVER_ADDRESS")
    return f"http://{ADDRESS}:9000/{DEFAULT_BUCKET}/{filename}"


async def download_file(filename: str) -> bytes:
    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name

        client = get_minio_client()
        client.fget_object(
            bucket_name=DEFAULT_BUCKET, object_name=filename, file_path=temp_path
        )

        with open(temp_path, "rb") as file:
            data = file.read()

        os.unlink(temp_path)
        return data
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {str(e)}")
        raise
