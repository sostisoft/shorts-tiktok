"""
saas/storage/s3.py
S3/MinIO client for video storage with presigned URLs.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from saas.config import get_settings

logger = logging.getLogger("saas.storage")

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        settings = get_settings()
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=BotoConfig(signature_version="s3v4"),
        )
        _ensure_bucket(settings.s3_bucket)
    return _s3_client


def _ensure_bucket(bucket: str):
    client = _s3_client
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        logger.info(f"Creating S3 bucket: {bucket}")
        client.create_bucket(Bucket=bucket)


def s3_key_for_tenant(tenant_id: str, job_id: str, filename: str) -> str:
    """Generate S3 key with tenant isolation: tenants/{tenant_id}/videos/{job_id}/{filename}"""
    return f"tenants/{tenant_id}/videos/{job_id}/{filename}"


def upload_file(local_path: str | Path, s3_key: str) -> str:
    """Upload a local file to S3. Returns the S3 key."""
    settings = get_settings()
    client = get_s3_client()
    client.upload_file(str(local_path), settings.s3_bucket, s3_key)
    logger.info(f"Uploaded {local_path} -> s3://{settings.s3_bucket}/{s3_key}")
    return s3_key


def download_file(s3_key: str, local_path: str | Path) -> Path:
    """Download a file from S3 to local path."""
    settings = get_settings()
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    client = get_s3_client()
    client.download_file(settings.s3_bucket, s3_key, str(local_path))
    return local_path


def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for downloading a file."""
    settings = get_settings()
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def delete_file(s3_key: str):
    """Delete a file from S3."""
    settings = get_settings()
    client = get_s3_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=s3_key)


def delete_tenant_job(tenant_id: str, job_id: str):
    """Delete all files for a specific job."""
    settings = get_settings()
    client = get_s3_client()
    prefix = f"tenants/{tenant_id}/videos/{job_id}/"
    response = client.list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix)
    for obj in response.get("Contents", []):
        client.delete_object(Bucket=settings.s3_bucket, Key=obj["Key"])


def cleanup_old_videos(days: int = 90):
    """Delete all S3 objects older than `days` days."""
    settings = get_settings()
    client = get_s3_client()
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix="tenants/"):
        for obj in page.get("Contents", []):
            if obj["LastModified"].timestamp() < cutoff:
                client.delete_object(Bucket=settings.s3_bucket, Key=obj["Key"])
                logger.info(f"Cleaned up old S3 object: {obj['Key']}")
