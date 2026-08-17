"""Shared audio/document import into a catalog text field + source file."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.schemas import ImportTextOut
from app.services.ingestion.lesson_content_import_service import (
    append_imported_text,
    classify_source,
    import_lesson_text,
)
from app.services.storage import get_storage
from app.services.upload_validation import (
    ATTACHMENT_MAX_BYTES,
    AUDIO_MAX_BYTES,
    LESSON_IMPORT_DOC_BY_EXT,
    is_allowed_report_audio,
    read_upload,
    resolve_allowed_type,
)


@dataclass(frozen=True)
class CatalogSourceImport:
    text: str
    storage_key: str
    filename: str
    content_type: str
    kind: str

    def to_out(self) -> ImportTextOut:
        return ImportTextOut(
            text=self.text,
            content_source_filename=self.filename,
            content_source_content_type=self.content_type,
            content_source_kind=self.kind,
        )


async def import_catalog_source(
    source: UploadFile,
    *,
    base_text: str | None,
    current_text: str,
    previous_storage_key: str | None,
    storage_prefix: str,
) -> CatalogSourceImport:
    """Transcribe/extract, append to catalog text, replace the stored source file."""
    filename = source.filename or ""
    try:
        kind = classify_source(filename)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    if kind == "audio":
        if not is_allowed_report_audio(source.content_type, filename):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo deve ser de áudio")
        content_type = source.content_type or "audio/webm"
        ext = Path(filename).suffix.lower() or ".webm"
        content = await read_upload(
            source,
            max_bytes=AUDIO_MAX_BYTES,
            too_large_message="Áudio muito grande (máx. 25 MB)",
            empty_message="Áudio vazio",
        )
    else:
        content_type, ext = resolve_allowed_type(source, LESSON_IMPORT_DOC_BY_EXT)
        content = await read_upload(
            source,
            max_bytes=ATTACHMENT_MAX_BYTES,
            too_large_message="Arquivo muito grande (máx. 10 MB)",
            empty_message="Arquivo vazio",
        )

    try:
        extracted = await import_lesson_text(
            content=content, filename=filename or f"source{ext}"
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except Exception as exc:
        detail = (
            "Não foi possível transcrever o áudio. Tente novamente."
            if kind == "audio"
            else "Não foi possível extrair o texto do arquivo. Tente novamente."
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail) from exc

    if not extracted.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Nenhum texto foi obtido. Verifique o áudio ou se o PDF tem texto selecionável.",
        )

    storage = get_storage()
    if previous_storage_key:
        await storage.delete(previous_storage_key)

    stored_name = filename or f"source{ext}"
    key = f"{storage_prefix}/{uuid.uuid4()}{ext}"
    await storage.save(content, key, content_type=content_type)

    base = current_text if base_text is None else base_text
    return CatalogSourceImport(
        text=append_imported_text(base, extracted),
        storage_key=key,
        filename=stored_name,
        content_type=content_type,
        kind=kind,
    )
