"""Shared helpers for multipart file uploads."""

from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.services.lesson_completion_service import StoredFile

# extension -> preferred content-type
TRACK_MATERIAL_BY_EXT = {
    ".pdf": "application/pdf",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

REPORT_ATTACHMENT_BY_EXT = {
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

AUDIO_MAX_BYTES = 25 * 1024 * 1024
MATERIAL_MAX_BYTES = 20 * 1024 * 1024
ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024


def _extension(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


def resolve_allowed_type(
    upload: UploadFile,
    by_ext: dict[str, str],
) -> tuple[str, str]:
    """Resolve content_type + extension from filename (browsers often send octet-stream)."""
    ext = _extension(upload.filename)
    if ext not in by_ext:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Tipo de arquivo não permitido ({ext or 'sem extensão'})",
        )
    declared = (upload.content_type or "").split(";")[0].strip().lower()
    if declared and declared not in ("application/octet-stream", "binary/octet-stream"):
        return declared, ext
    return by_ext[ext], ext


async def read_upload(
    upload: UploadFile,
    *,
    max_bytes: int,
    too_large_message: str,
    empty_message: str = "Arquivo vazio",
) -> bytes:
    content = await upload.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, empty_message)
    if len(content) > max_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, too_large_message)
    return content


def is_audio_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    ct = content_type.split(";")[0].strip().lower()
    return ct.startswith("audio/") or ct == "video/webm"


def _has_upload(upload: UploadFile | None) -> bool:
    return upload is not None and bool(upload.filename)


async def parse_report_attachment(upload: UploadFile | None) -> StoredFile | None:
    if not _has_upload(upload):
        return None
    assert upload is not None
    content_type, ext = resolve_allowed_type(upload, REPORT_ATTACHMENT_BY_EXT)
    content = await read_upload(
        upload,
        max_bytes=ATTACHMENT_MAX_BYTES,
        too_large_message="Anexo muito grande (máx. 10 MB)",
    )
    return StoredFile(
        content=content,
        filename=upload.filename or f"anexo{ext}",
        content_type=content_type,
        extension=ext,
    )


async def parse_report_audio(upload: UploadFile | None) -> StoredFile | None:
    if not _has_upload(upload):
        return None
    assert upload is not None
    if not is_audio_content_type(upload.content_type):
        ext = _extension(upload.filename)
        if ext not in {".webm", ".ogg", ".mp3", ".wav", ".m4a", ".mpeg"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo deve ser de áudio")
    content = await read_upload(
        upload,
        max_bytes=AUDIO_MAX_BYTES,
        too_large_message="Áudio muito grande (máx. 25 MB)",
    )
    ext = _extension(upload.filename) or ".webm"
    content_type = (upload.content_type or "audio/webm").split(";")[0].strip().lower()
    if content_type in ("application/octet-stream", "binary/octet-stream", ""):
        content_type = "audio/webm"
    return StoredFile(
        content=content,
        filename=upload.filename or f"relato{ext}",
        content_type=content_type,
        extension=ext,
    )
