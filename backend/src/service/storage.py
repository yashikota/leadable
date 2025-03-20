import minio
import os
from pathlib import Path
from io import BufferedIOBase  # Importing to use as a base class for binary I/O

# MinIO client configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "root")
MINIO_SECRET_KEY = os.getenv("MINIO_PASSWORD")
DEFAULT_BUCKET = os.getenv("MINIO_DEFAULT_BUCKET", "leadable")


def get_minio_client() -> minio.Minio:
    """
    Initialize and return a MinIO client.
    """
    return minio.Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def ensure_bucket_exists(client: minio.Minio, bucket_name: str) -> None:
    """
    Ensure that the specified bucket exists, creating it if necessary.
    """
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


def upload_file(
    file_path_or_object: str
    | Path
    | BufferedIOBase,  # Using BufferedIOBase as a more generic binary I/O base class
    object_name: str | None = None,
    bucket_name: str = DEFAULT_BUCKET,
    content_type: str | None = None,
) -> str:
    """
    Upload a file to MinIO storage.

    Args:
        file_path_or_object: Path to the file or a file-like object
        object_name: Name to save the file as in MinIO (defaults to basename if file_path is provided)
        bucket_name: Name of the bucket to upload to
        content_type: MIME type of the file (optional)

    Returns:
        The object name of the uploaded file
    """
    client = get_minio_client()
    ensure_bucket_exists(client, bucket_name)

    # If file_path_or_object is a string or Path, open the file
    if isinstance(file_path_or_object, (str, Path)):
        file_path = Path(file_path_or_object)
        if not object_name:
            object_name = file_path.name

        client.fput_object(
            bucket_name=bucket_name,
            object_name=object_name,
            file_path=str(file_path),
            content_type=content_type,
        )
    else:
        # It's a file-like object
        if not object_name:
            raise ValueError(
                "object_name must be specified when uploading from a file-like object"
            )

        # To get the size, we need to read the file
        file_data = file_path_or_object.read()
        file_size = len(file_data)
        file_path_or_object.seek(0)  # Reset file pointer

        client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=file_path_or_object,
            length=file_size,
            content_type=content_type,
        )

    return object_name


def download_file(
    object_name: str,
    file_path: str | Path | None = None,
    bucket_name: str = DEFAULT_BUCKET,
) -> bytes | str:
    """
    Download a file from MinIO storage.

    Args:
        object_name: Name of the file in MinIO
        file_path: Path where to save the downloaded file (optional)
        bucket_name: Name of the bucket to download from

    Returns:
        If file_path is provided, returns the file path.
        Otherwise, returns the file content as bytes.
    """
    client = get_minio_client()

    if file_path:
        file_path = Path(file_path)
        client.fget_object(
            bucket_name=bucket_name, object_name=object_name, file_path=str(file_path)
        )
        return str(file_path)
    else:
        # Return the file content as bytes
        response = client.get_object(bucket_name=bucket_name, object_name=object_name)
        data = response.read()
        response.close()
        return data
