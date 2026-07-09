"""Local filesystem storage for development."""

from pathlib import Path

from app.core.config import settings


class LocalStorage:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.STORAGE_LOCAL_ROOT)

    def _path(self, key: str) -> Path:
        # Prevent path traversal outside the media root.
        root = self.root.resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Invalid storage key")
        return path

    async def save(self, content: bytes, key: str, content_type: str | None = None) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    async def open(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()
