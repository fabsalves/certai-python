"""Transcrição de áudio via Groq Whisper (síncrona, para revisão antes do envio)."""

from __future__ import annotations

import logging

from groq import AsyncGroq

from app.core.config import settings

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


async def transcribe_audio(content: bytes, filename: str = "audio.webm") -> str:
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
