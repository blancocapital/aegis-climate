import hashlib

import boto3
from botocore.client import Config

from app.core.config import get_settings

settings = get_settings()


def get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket():
    client = get_client()
    buckets = client.list_buckets().get("Buckets", [])
    if not any(b.get("Name") == settings.minio_bucket for b in buckets):
        client.create_bucket(Bucket=settings.minio_bucket)


def compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    ensure_bucket()
    client = get_client()
    client.put_object(Bucket=settings.minio_bucket, Key=key, Body=data, ContentType=content_type)
    return f"s3://{settings.minio_bucket}/{key}"


def get_object(key: str) -> bytes:
    client = get_client()
    resp = client.get_object(Bucket=settings.minio_bucket, Key=key)
    return resp["Body"].read()
