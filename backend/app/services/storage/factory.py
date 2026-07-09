"""Resolve the configured storage backend."""

from functools import lru_cache

from app.core.config import settings
from app.services.storage.local_storage import LocalStorage
from app.services.storage.s3_storage import S3Storage


@lru_cache
def get_storage() -> LocalStorage | S3Storage:
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage()
