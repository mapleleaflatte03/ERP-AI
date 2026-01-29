"""
ERPX AI Accounting - MinIO Storage Module
==========================================
Object storage operations for raw document uploads.
"""

import hashlib
import io
import logging
import os
import uuid
from datetime import datetime
from typing import BinaryIO, Optional, Tuple

from minio import Minio
from minio.error import S3Error

from src.core import config

logger = logging.getLogger(__name__)

# =============================================================================
# MinIO Client
# =============================================================================

_client: Minio | None = None


def get_minio_client() -> Minio:
    """Get or create MinIO client"""
    global _client
    if _client is None:
        _client = Minio(
            config.MINIO_ENDPOINT,
            access_key=config.MINIO_ACCESS_KEY,
            secret_key=config.MINIO_SECRET_KEY,
            secure=config.MINIO_SECURE,
        )
        logger.info(f"MinIO client initialized: {config.MINIO_ENDPOINT}")
    return _client


def ensure_bucket(bucket_name: str):
    """Ensure bucket exists, create if not"""
    client = get_minio_client()
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info(f"Created bucket: {bucket_name}")
    except S3Error as e:
        logger.error(f"Error ensuring bucket {bucket_name}: {e}")
        raise


# =============================================================================
# Upload Operations
# =============================================================================


def upload_document_v2(
    file_data: bytes,
    filename: str,
    content_type: str,
    tenant_id: str = "default",
    job_id: str | None = None,
) -> tuple[str, str, str, int]:
    """
    Upload document to MinIO.

    Returns:
        Tuple of (bucket, key, checksum, size)
    """
    client = get_minio_client()
    bucket = config.MINIO_BUCKET

    # Ensure bucket exists
    ensure_bucket(bucket)

    # Generate job_id if not provided
    if not job_id:
        job_id = str(uuid.uuid4())

    # Calculate checksum
    checksum = hashlib.sha256(file_data).hexdigest()

    # Build key path: raw/{tenant_id}/{yyyy}/{mm}/{job_id}/{filename}
    now = datetime.utcnow()
    key = f"raw/{tenant_id}/{now.year}/{now.month:02d}/{job_id}/{filename}"

    # Upload to MinIO
    try:
        client.put_object(
            bucket,
            key,
            io.BytesIO(file_data),
            length=len(file_data),
            content_type=content_type,
            metadata={
                "job_id": job_id,
                "tenant_id": tenant_id,
                "original_filename": filename,
                "checksum": checksum,
                "uploaded_at": now.isoformat(),
            },
        )
        logger.info(f"Uploaded document to minio://{bucket}/{key} ({len(file_data)} bytes)")
        return bucket, key, checksum, len(file_data)

    except S3Error as e:
        logger.error(f"Failed to upload to MinIO: {e}")
        raise


def upload_file_object(
    file_obj: BinaryIO,
    filename: str,
    content_type: str,
    file_size: int,
    tenant_id: str = "default",
    job_id: str | None = None,
) -> tuple[str, str, str, int]:
    """
    Upload file object to MinIO.

    Returns:
        Tuple of (bucket, key, checksum, size)
    """
    # Read file data for checksum calculation
    file_data = file_obj.read()
    file_obj.seek(0)  # Reset for potential re-read

    return upload_document_v2(
        file_data=file_data,
        filename=filename,
        content_type=content_type,
        tenant_id=tenant_id,
        job_id=job_id,
    )


# =============================================================================
# Download Operations
# =============================================================================


def download_document(bucket: str, key: str) -> bytes:
    """Download document from MinIO"""
    client = get_minio_client()
    try:
        response = client.get_object(bucket, key)
        data = response.read()
        response.close()
        response.release_conn()
        logger.info(f"Downloaded document from minio://{bucket}/{key}")
        return data
    except S3Error as e:
        logger.error(f"Failed to download from MinIO: {e}")
        raise


def stream_document(bucket: str, key: str):
    """
    Get a streamable response from MinIO.
    Returns (response_object, content_type, size)
    """
    client = get_minio_client()
    try:
        response = client.get_object(bucket, key)
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        size = response.headers.get("Content-Length")
        return response, content_type, size
    except S3Error as e:
        logger.error(f"Failed to stream from MinIO: {e}")
        raise


def get_document_url(bucket: str, key: str, expires_hours: int = 1) -> str:
    """Get presigned URL for document"""
    from datetime import timedelta

    client = get_minio_client()
    try:
        url = client.presigned_get_object(bucket, key, expires=timedelta(hours=expires_hours))
        return url
    except S3Error as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        raise


def document_exists(bucket: str, key: str) -> bool:
    """Check if document exists in MinIO"""
    client = get_minio_client()
    try:
        client.stat_object(bucket, key)
        return True
    except S3Error:
        return False


def get_document_metadata(bucket: str, key: str) -> dict | None:
    """Get document metadata"""
    client = get_minio_client()
    try:
        stat = client.stat_object(bucket, key)
        return {
            "size": stat.size,
            "etag": stat.etag,
            "content_type": stat.content_type,
            "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
            "metadata": dict(stat.metadata) if stat.metadata else {},
        }
    except S3Error:
        return None


# =============================================================================
# Delete Operations
# =============================================================================


def delete_document(bucket: str, key: str):
    """Delete document from MinIO"""
    client = get_minio_client()
    try:
        client.remove_object(bucket, key)
        logger.info(f"Deleted document from minio://{bucket}/{key}")
    except S3Error as e:
        logger.error(f"Failed to delete from MinIO: {e}")
        raise


# =============================================================================
# List Operations
# =============================================================================


def list_documents(bucket: str, prefix: str = "", limit: int = 1000) -> list:
    """List documents in bucket with prefix"""
    client = get_minio_client()
    try:
        objects = client.list_objects(bucket, prefix=prefix, recursive=True)
        result = []
        for obj in objects:
            if len(result) >= limit:
                break
            result.append(
                {
                    "key": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "etag": obj.etag,
                }
            )
        return result
    except S3Error as e:
        logger.error(f"Failed to list objects: {e}")
        raise


__all__ = [
    "get_minio_client",
    "ensure_bucket",
    "upload_document_v2",
    "upload_file_object",
    "download_document",
    "stream_document",
    "get_document_url",
    "document_exists",
    "get_document_metadata",
    "delete_document",
    "list_documents",
]
