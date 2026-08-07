"""Ephemeral import of lesson content from audio or document (no storage)."""

from __future__ import annotations

import re
from pathlib import Path

from app.services.ingestion.extraction import UnsupportedFormatError, extract_text
from app.services.transcription_service import transcribe_audio

AUDIO_EXTENSIONS = {".webm", ".ogg", ".mp3", ".wav", ".m4a", ".mpeg"}
DOCUMENT_EXTENSIONS = {".txt", ".docx", ".pdf", ".pptx"}


def classify_source(filename: str | None) -> str:
    """Return 'audio' or 'document'."""
    ext = Path(filename or "").suffix.lower()
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    raise ValueError(
        f"Tipo de arquivo não permitido ({ext or 'sem extensão'}). "
        "Use áudio (webm, ogg, mp3, wav, m4a) ou documento (txt, docx, pdf, pptx)."
    )


def _normalize_transcript(transcript: str) -> str:
    """Whitespace-only cleanup — no LLM rewrite."""
    text = transcript.replace("\r\n", "\n").strip()
    if not text:
        return ""
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def append_imported_text(existing: str | None, incoming: str) -> str:
    """Append imported text like a chat attachment (blank line between blocks)."""
    base = (existing or "").replace("\r\n", "\n").strip()
    addition = (incoming or "").replace("\r\n", "\n").strip()
    if not addition:
        return base
    if not base:
        return addition
    return f"{base}\n\n{addition}"


async def import_lesson_text(*, content: bytes, filename: str) -> str:
    """Process upload in memory and return text for the lesson content field."""
    kind = classify_source(filename)
    if kind == "audio":
        transcript = await transcribe_audio(content, filename=filename)
        return _normalize_transcript(transcript)

    try:
        return extract_text(content, Path(filename).suffix.lower())
    except UnsupportedFormatError as exc:
        raise ValueError(str(exc)) from exc
