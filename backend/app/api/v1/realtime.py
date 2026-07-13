"""Realtime voice endpoints — Etapa B: handoff token + validação pública."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.engine import SYSTEM_BASE
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_roles
from app.models.cohort import Cohort
from app.models.conversation import Conversation, ConversationChannel
from app.models.track import Lesson, Track
from app.models.user import Role, User
from app.services.realtime.handoff_token_service import HandoffClaims, HandoffTokenError, HandoffTokenService
from app.services.realtime.openai_realtime_service import OpenaiRealtimeError, OpenaiRealtimeService

router = APIRouter(prefix="/realtime", tags=["realtime"])

_handoff_service = HandoffTokenService()


def _first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else full_name


def _handoff_http_error(exc: HandoffTokenError) -> HTTPException:
    if exc.expired:
        return HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Este link de voz expirou. Volte ao WhatsApp e peça um novo convite.",
        )
    return HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc))


class HandoffGenerateIn(BaseModel):
    cohort_id: uuid.UUID
    user_id: uuid.UUID
    lesson_id: uuid.UUID


class HandoffGenerateOut(BaseModel):
    url: str
    token: str
    expires_at: int


class SessionValidateIn(BaseModel):
    handoff_token: str


class SessionValidateOut(BaseModel):
    valid: bool = True
    student_first_name: str
    lesson_title: str
    track_title: str
    assistant_name: str
    expires_at: int


class RealtimeTokenIn(BaseModel):
    handoff_token: str


class RealtimeTokenOut(BaseModel):
    ephemeral_token: str
    expires_at: int
    realtime_model: str
    realtime_voice: str
    play_session_opener: bool = True


async def _load_session_context(
    db: AsyncSession,
    claims: HandoffClaims,
) -> tuple[str, str, str, str]:
    student = await db.get(User, claims.user_id)
    if student is None or not student.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aluno não encontrado")

    lesson = await db.get(Lesson, claims.lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")

    cohort = await db.get(Cohort, claims.cohort_id)
    if cohort is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turma não encontrada")

    track_title = await db.scalar(select(Track.title).where(Track.id == cohort.track_id))
    return (
        _first_name(student.name),
        lesson.title,
        track_title or "",
        settings.ASSISTANT_NAME,
    )


def _handoff_instructions(
    *,
    student_first_name: str,
    lesson_title: str,
    track_title: str,
) -> str:
    return f"""{SYSTEM_BASE}

## Modo de conversa
Você está em uma chamada de voz ao vivo. Respostas curtas e naturais para fala.
Não use markdown, listas longas ou formatação. Uma ideia por vez.

## Contexto da aula
Aula: {lesson_title}
Trilha: {track_title}

## Abertura
Cumprimente o aluno pelo nome ({student_first_name}) e retome de onde a conversa parou.
Não recomece do zero se já houve troca de mensagens."""


@router.post("/handoff/generate", response_model=HandoffGenerateOut)
async def generate_handoff_token(
    body: HandoffGenerateIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN, Role.PROFESSOR)),
) -> HandoffGenerateOut:
    """Gera link de handoff (48h, reusável). Usado no dispatch na Etapa E; aqui para testes."""
    student = await db.get(User, body.user_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aluno não encontrado")

    lesson = await db.get(Lesson, body.lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")

    conversation_id = await db.scalar(
        select(Conversation.id).where(
            Conversation.cohort_id == body.cohort_id,
            Conversation.user_id == body.user_id,
            Conversation.lesson_id == body.lesson_id,
            Conversation.channel == ConversationChannel.WHATSAPP,
        )
    )

    token, expires_at = _handoff_service.generate(
        user_id=body.user_id,
        cohort_id=body.cohort_id,
        lesson_id=body.lesson_id,
        conversation_id=conversation_id,
    )
    return HandoffGenerateOut(
        url=_handoff_service.build_url(token),
        token=token,
        expires_at=int(expires_at.timestamp()),
    )


@router.post("/session/validate", response_model=SessionValidateOut)
async def validate_session(
    body: SessionValidateIn,
    db: AsyncSession = Depends(get_db),
) -> SessionValidateOut:
    """Valida handoff token sem consumir (read-only para UI)."""
    try:
        claims = _handoff_service.validate_readonly(body.handoff_token)
    except HandoffTokenError as exc:
        raise _handoff_http_error(exc) from exc

    student_first_name, lesson_title, track_title, assistant_name = await _load_session_context(
        db, claims
    )
    return SessionValidateOut(
        student_first_name=student_first_name,
        lesson_title=lesson_title,
        track_title=track_title,
        assistant_name=assistant_name,
        expires_at=int(claims.expires_at.timestamp()),
    )


@router.post("/token", response_model=RealtimeTokenOut)
async def create_realtime_token(
    body: RealtimeTokenIn,
    db: AsyncSession = Depends(get_db),
) -> RealtimeTokenOut:
    """Gera ephemeral token OpenAI para WebRTC a partir de handoff token válido."""
    try:
        claims = _handoff_service.validate_readonly(body.handoff_token)
    except HandoffTokenError as exc:
        raise _handoff_http_error(exc) from exc

    student_first_name, lesson_title, track_title, _assistant = await _load_session_context(
        db, claims
    )
    instructions = _handoff_instructions(
        student_first_name=student_first_name,
        lesson_title=lesson_title,
        track_title=track_title,
    )

    try:
        service = OpenaiRealtimeService()
        secret = await service.create_client_secret(instructions=instructions)
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
