"""Realtime voice endpoints — Etapa A: POC com IDs/instructions hardcoded."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.ai.engine import SYSTEM_BASE
from app.core.config import settings
from app.services.realtime.openai_realtime_service import OpenaiRealtimeError, OpenaiRealtimeService

router = APIRouter(prefix="/realtime", tags=["realtime"])

# Etapa A — substituídos por handoff token + ContextBuilder na Etapa B/D.
POC_COHORT_ID = uuid.UUID("4409cef2-e1a4-47d4-aa57-4c95a0698e78")
POC_LESSON_ID = uuid.UUID("ec0d3ef0-869b-4d30-aeeb-13e48cb91607")
POC_STUDENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
POC_STUDENT_FIRST_NAME = "Estudante"


class RealtimeTokenOut(BaseModel):
    ephemeral_token: str
    expires_at: int
    realtime_model: str
    realtime_voice: str
    play_session_opener: bool = True


def _poc_instructions() -> str:
    return f"""{SYSTEM_BASE}

## Modo de conversa
Você está em uma chamada de voz ao vivo. Respostas curtas e naturais para fala.
Não use markdown, listas longas ou formatação. Uma ideia por vez.

## Contexto (POC Etapa A)
Turma: {POC_COHORT_ID}
Aula: {POC_LESSON_ID}
Aluno: {POC_STUDENT_ID}

## Abertura
Cumprimente o aluno pelo nome ({POC_STUDENT_FIRST_NAME}) e pergunte como pode ajudar na aula.
Não recomece do zero se já houve troca de mensagens — nesta POC, trate como primeira conversa."""


@router.post("/token", response_model=RealtimeTokenOut)
async def create_realtime_token() -> RealtimeTokenOut:
    """Gera ephemeral token OpenAI para WebRTC (POC Etapa A, sem handoff)."""
    try:
        service = OpenaiRealtimeService()
        secret = await service.create_client_secret(instructions=_poc_instructions())
    except OpenaiRealtimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    expires_at = secret.get("expires_at")
    if expires_at is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenAI não retornou expires_at")

    return RealtimeTokenOut(
        ephemeral_token=secret["value"],
        expires_at=int(expires_at),
        realtime_model=secret.get("model") or settings.OPENAI_REALTIME_MODEL,
        realtime_voice=secret.get("voice") or settings.OPENAI_REALTIME_VOICE,
        play_session_opener=True,
    )
