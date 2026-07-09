"""Build authenticated file download responses from storage."""

from urllib.parse import quote

from fastapi import HTTPException, status
from fastapi.responses import Response

from app.services.storage import get_storage


async def file_response(
    *,
    storage_key: str | None,
    filename: str,
    content_type: str | None = None,
) -> Response:
    if not storage_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado")

    storage = get_storage()
    try:
        content = await storage.open(storage_key)
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado") from e

    ascii_name = filename.encode("ascii", "ignore").decode() or "download"
    disposition = (
        f"attachment; filename=\"{ascii_name}\"; "
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=content,
        media_type=content_type or "application/octet-stream",
        headers={"Content-Disposition": disposition},
    )
