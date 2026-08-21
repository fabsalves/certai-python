"""Transcrição de áudio via Groq Whisper (síncrona, para revisão antes do envio)."""

from __future__ import annotations

import logging

from groq import AsyncGroq
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.usage import UsageScope, record_groq_transcription

logger = logging.getLogger(__name__)

# Primes Whisper vocabulary/spelling for Brazilian Portuguese + product terms.
# Does not rewrite after the fact — only biases STT decoding.
_TRANSCRIBE_PROMPT_PT = (
    "Transcrição em português do Brasil. Vocabulário possível: CertAI, Certai, "
    "call, WhatsApp, feedback, tutorial, Horácio, Fabiano, Pedro, trilha, aula, "
    "módulo, turma, professor, aluno, mão na massa."
)


def _text_from_response(resp: object) -> str:
    """Prefer segment join (natural pauses) when verbose_json is available."""
    segments = getattr(resp, "segments", None)
    if segments:
        parts: list[str] = []
        for seg in segments:
            piece = (getattr(seg, "text", None) or "").strip()
            if piece:
                parts.append(piece)
        if parts:
            return "\n\n".join(parts)
    return (getattr(resp, "text", None) or "").strip()


def _duration_seconds(resp: object) -> float | None:
    """verbose_json reports the audio duration; Whisper is billed by the hour."""
    value = getattr(resp, "duration", None)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def transcribe_audio(
    content: bytes,
    filename: str = "audio.webm",
    *,
    db: AsyncSession | None = None,
    scope: UsageScope | None = None,
    usage_event_id: str | None = None,
) -> str:
    """`db`/`scope`/`usage_event_id` are optional: metering only happens when the
    caller knows who to charge. Duration comes from the verbose_json response, so
    the json fallback path is not metered -- it has no duration to bill."""
    if not settings.GROQ_API_KEY:
        raise RuntimeError("Transcrição indisponível: GROQ_API_KEY não configurada")

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    common = dict(
        file=(filename, content),
        model=settings.GROQ_TRANSCRIBE_MODEL,
        language="pt",
        temperature=0.0,
        prompt=_TRANSCRIBE_PROMPT_PT,
    )

    try:
        resp = await client.audio.transcriptions.create(
            **common,
            response_format="verbose_json",
        )
        text = _text_from_response(resp)
        if text:
            if db is not None and usage_event_id:
                await record_groq_transcription(
                    db,
                    scope=scope or UsageScope(),
                    model=settings.GROQ_TRANSCRIBE_MODEL,
                    provider_event_id=usage_event_id,
                    seconds=_duration_seconds(resp),
                )
            return text
    except Exception:
        logger.warning(
            "verbose_json transcription failed; falling back to json",
            exc_info=True,
        )

    resp = await client.audio.transcriptions.create(
        **common,
        response_format="json",
    )
    return (getattr(resp, "text", None) or "").strip()
