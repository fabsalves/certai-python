"""AWS S3 storage for staging/production."""

import asyncio

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class S3Storage:
    def __init__(self) -> None:
        if not settings.AWS_BUCKET:
            raise RuntimeError("AWS_BUCKET is required when STORAGE_BACKEND=s3")
        kwargs: dict = {"region_name": settings.AWS_REGION}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        self._client = boto3.client("s3", **kwargs)
        self._bucket = settings.AWS_BUCKET

    async def save(self, content: bytes, key: str, content_type: str | None = None) -> str:
        extra: dict = {}
        if content_type:
            extra["ContentType"] = content_type

        def _put() -> None:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=content, **extra)

        await asyncio.to_thread(_put)
        return key

    async def open(self, key: str) -> bytes:
        def _get() -> bytes:
            try:
                resp = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code in {"404", "NoSuchKey", "NotFound"}:
                    raise FileNotFoundError(key) from e
                raise
            return resp["Body"].read()

        return await asyncio.to_thread(_get)

    async def delete(self, key: str) -> None:
        def _delete() -> None:
            try:
                self._client.delete_object(Bucket=self._bucket, Key=key)
            except ClientError:
                pass

        await asyncio.to_thread(_delete)
