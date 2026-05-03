"""
Object storage service (MinIO / AWS S3 compatible).
"""
import logging
from io import BytesIO

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

_s3_client = None


def _get_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        # Ensure bucket exists
        try:
            _s3_client.head_bucket(Bucket=settings.S3_BUCKET_RESUMES)
        except ClientError:
            _s3_client.create_bucket(Bucket=settings.S3_BUCKET_RESUMES)
            logger.info(f"Created bucket: {settings.S3_BUCKET_RESUMES}")
    return _s3_client


async def upload_file_to_s3(file_bytes: bytes, key: str, content_type: str) -> str:
    """Upload bytes to S3/MinIO. Returns the object key."""
    client = _get_client()
    client.put_object(
        Bucket=settings.S3_BUCKET_RESUMES,
        Key=key,
        Body=BytesIO(file_bytes),
        ContentType=content_type,
        ContentLength=len(file_bytes),
    )
    logger.info(f"Uploaded {key} ({len(file_bytes)} bytes)")
    return key


async def download_file_from_s3(key: str) -> bytes:
    """Download file bytes from S3/MinIO."""
    client = _get_client()
    response = client.get_object(Bucket=settings.S3_BUCKET_RESUMES, Key=key)
    return response["Body"].read()


async def delete_file_from_s3(key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=settings.S3_BUCKET_RESUMES, Key=key)
    logger.info(f"Deleted {key}")


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a temporary download URL for secure file access."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_RESUMES, "Key": key},
        ExpiresIn=expires_in,
    )
