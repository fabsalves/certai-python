"""Storage backend protocol — local disk or S3."""

from typing import Protocol


class StorageBackend(Protocol):
    async def save(self, content: bytes, key: str, content_type: str | None = None) -> str:
        """Persist bytes at key. Returns the storage key."""
        ...

    async def open(self, key: str) -> bytes:
        """Read bytes for key. Raises FileNotFoundError when missing."""
        ...

    async def delete(self, key: str) -> None:
        """Remove object if it exists. No-op when missing."""
        ...
