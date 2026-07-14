"""Voice session lifecycle, lock, turn relay and heartbeat."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Author, Conversation, ConversationChannel, Message, MessageSource
from app.models.voice_session import VoiceSession, VoiceSessionStatus
from app.services.conversation_service import get_or_create_conversation, record_message
from app.services.realtime.handoff_token_service import HandoffClaims

LOCK_TTL_SECONDS = 90
_ACTIVE_STATUSES = (
    VoiceSessionStatus.CREATED,
    VoiceSessionStatus.ACTIVE,
    VoiceSessionStatus.RECONNECTING,
)


class VoiceSessionError(Exception):
    pass


class VoiceSessionLockedByOther(VoiceSessionError):
    pass


class VoiceSessionLockInvalid(VoiceSessionError):
    pass


@dataclass(frozen=True)
class TurnInput:
    idempotency_key: str
    author: Author
    content: str
    realtime_item_id: str
    sequence: int


@dataclass(frozen=True)
class TurnRelayResult:
    accepted: int
    duplicates: int
    conversation_id: uuid.UUID


@dataclass(frozen=True)
class EndSessionResult:
    status: VoiceSessionStatus
    turn_count: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_lock_token() -> str:
    return secrets.token_urlsafe(32)


class VoiceSessionService:
    async def begin_session(
        self,
        db: AsyncSession,
        claims: HandoffClaims,
        *,
        reconnect_from_session_id: uuid.UUID | None = None,
    ) -> VoiceSession:
        conversation = await get_or_create_conversation(
            db,
            claims.cohort_id,
            claims.user_id,
            claims.lesson_id,
            channel=ConversationChannel.REALTIME_VOICE,
        )

        await self._close_stale_sessions(db, conversation.id)

        if reconnect_from_session_id is not None:
            await self._end_session_by_id(
                db,
                reconnect_from_session_id,
                conversation_id=conversation.id,
                reason="replaced",
            )

        active = await self._active_session(db, conversation.id)
        if active is not None:
            raise VoiceSessionLockedByOther(
                "Sessão de voz aberta em outro dispositivo ou aba."
            )

        now = _utcnow()
        session = VoiceSession(
            conversation_id=conversation.id,
            status=VoiceSessionStatus.CREATED,
            lock_token=_new_lock_token(),
            lock_expires_at=now + timedelta(seconds=LOCK_TTL_SECONDS),
            last_heartbeat_at=now,
        )
        db.add(session)
        await db.flush()
        return session

    async def assert_lock(
        self,
        db: AsyncSession,
        voice_session_id: uuid.UUID,
        lock_token: str,
    ) -> VoiceSession:
        session = await db.get(VoiceSession, voice_session_id)
        if session is None:
            raise VoiceSessionLockInvalid("Sessão de voz não encontrada")

        if session.status in (VoiceSessionStatus.ENDED, VoiceSessionStatus.ABANDONED):
            raise VoiceSessionLockInvalid("Sessão de voz já encerrada")

        if self._lock_stale(session):
            await self._mark_abandoned(db, session)
            raise VoiceSessionLockInvalid("Lock de voz expirado")

        if not secrets.compare_digest(session.lock_token, lock_token):
            raise VoiceSessionLockInvalid("Lock de voz inválido")

        now = _utcnow()
        session.lock_expires_at = now + timedelta(seconds=LOCK_TTL_SECONDS)
        session.last_heartbeat_at = now
        self._activate_if_needed(session)
        await db.flush()
        return session

    async def renew_heartbeat(
        self,
        db: AsyncSession,
        voice_session_id: uuid.UUID,
        lock_token: str,
    ) -> VoiceSession:
        session = await self.assert_lock(db, voice_session_id, lock_token)
        self._activate_if_needed(session)
        await db.flush()
        return session

    async def record_turns(
        self,
        db: AsyncSession,
        voice_session_id: uuid.UUID,
        lock_token: str,
        turns: list[TurnInput],
    ) -> TurnRelayResult:
        session = await self.assert_lock(db, voice_session_id, lock_token)
        self._activate_if_needed(session)

        conversation = await db.get(Conversation, session.conversation_id)
        if conversation is None:
            raise VoiceSessionLockInvalid("Conversa não encontrada")

        accepted = 0
        duplicates = 0
        for turn in turns:
            content = turn.content.strip()
            if not content:
                continue

            _, created = await record_message(
                db,
                conversation,
                turn.author,
                content,
                source=MessageSource.REALTIME_VOICE,
                idempotency_key=turn.idempotency_key,
            )
            if created:
                accepted += 1
            else:
                duplicates += 1

        if accepted > 0:
            conversation.updated_at = _utcnow()
            await db.flush()

        return TurnRelayResult(
            accepted=accepted,
            duplicates=duplicates,
            conversation_id=conversation.id,
        )

    async def end_session(
        self,
        db: AsyncSession,
        voice_session_id: uuid.UUID,
        lock_token: str,
        *,
        reason: str = "explicit",
        final_sequence: int | None = None,
    ) -> EndSessionResult:
        session = await self.assert_lock(db, voice_session_id, lock_token)
        turn_count = await self._session_turn_count(db, voice_session_id)

        if final_sequence is not None and final_sequence != turn_count:
            raise VoiceSessionError(
                f"Sequência final inconsistente: esperado {final_sequence}, persistido {turn_count}"
            )

        now = _utcnow()
        session.status = VoiceSessionStatus.ENDED
        session.ended_at = now
        session.end_reason = reason
        await db.flush()

        return EndSessionResult(status=session.status, turn_count=turn_count)

    async def _session_turn_count(
        self,
        db: AsyncSession,
        voice_session_id: uuid.UUID,
    ) -> int:
        prefix = f"{voice_session_id}:"
        return int(
            await db.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.idempotency_key.like(f"{prefix}%"))
            )
            or 0
        )

    def _activate_if_needed(self, session: VoiceSession) -> None:
        if session.status != VoiceSessionStatus.CREATED:
            return
        now = _utcnow()
        session.status = VoiceSessionStatus.ACTIVE
        session.started_at = now

    def _lock_stale(self, session: VoiceSession) -> bool:
        return session.lock_expires_at < _utcnow()

    async def _active_session(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> VoiceSession | None:
        return await db.scalar(
            select(VoiceSession)
            .where(
                VoiceSession.conversation_id == conversation_id,
                VoiceSession.status.in_(_ACTIVE_STATUSES),
            )
            .order_by(VoiceSession.created_at.desc())
            .limit(1)
        )

    async def _close_stale_sessions(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> None:
        sessions = (
            await db.scalars(
                select(VoiceSession).where(
                    VoiceSession.conversation_id == conversation_id,
                    VoiceSession.status.in_(_ACTIVE_STATUSES),
                )
            )
        ).all()
        for session in sessions:
            if self._lock_stale(session):
                await self._mark_abandoned(db, session)

    async def _end_session_by_id(
        self,
        db: AsyncSession,
        voice_session_id: uuid.UUID,
        *,
        conversation_id: uuid.UUID,
        reason: str,
    ) -> None:
        session = await db.get(VoiceSession, voice_session_id)
        if session is None or session.conversation_id != conversation_id:
            return
        if session.status in (VoiceSessionStatus.ENDED, VoiceSessionStatus.ABANDONED):
            return
        now = _utcnow()
        session.status = VoiceSessionStatus.ENDED
        session.ended_at = now
        session.end_reason = reason
        await db.flush()

    async def sweep_abandoned_sessions(self, db: AsyncSession) -> int:
        """Marca sessões ativas sem heartbeat dentro do TTL como abandoned."""
        now = _utcnow()
        sessions = (
            await db.scalars(
                select(VoiceSession).where(
                    VoiceSession.status.in_(_ACTIVE_STATUSES),
                    VoiceSession.lock_expires_at < now,
                )
            )
        ).all()
        for session in sessions:
            await self._mark_abandoned(db, session)
        return len(sessions)

    async def _mark_abandoned(self, db: AsyncSession, session: VoiceSession) -> None:
        now = _utcnow()
        session.status = VoiceSessionStatus.ABANDONED
        session.ended_at = now
        session.end_reason = "timeout"
        await db.flush()
