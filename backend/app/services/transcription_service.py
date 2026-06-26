"""Transcrição de áudio via Groq Whisper (síncrona, para revisão antes do envio)."""

from groq import AsyncGroq

from app.core.config import settings


async def transcribe_audio(content: bytes, filename: str = "audio.webm") -> str:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("Transcrição indisponível: GROQ_API_KEY não configurada")

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    resp = await client.audio.transcriptions.create(
        file=(filename, content),
        model=settings.GROQ_TRANSCRIBE_MODEL,
        language="pt",
    )
    return (resp.text or "").strip()
