"""Smoke checks for voice session abandon sweep (Etapa F)."""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, ".")

from app.models.voice_session import VoiceSession, VoiceSessionStatus
from app.services.realtime.voice_session_service import LOCK_TTL_SECONDS, VoiceSessionService
from app.workers.celery_app import celery_app


def test_beat_schedule_registers_abandon_sweep() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "voice-session-abandon-sweep" in schedule
    entry = schedule["voice-session-abandon-sweep"]
    assert entry["task"] == "app.workers.tasks.sweep_abandoned_voice_sessions"
    assert entry["schedule"] == 30.0


def test_lock_ttl_is_90_seconds() -> None:
    assert LOCK_TTL_SECONDS == 90


async def _test_sweep_marks_stale_sessions_abandoned() -> None:
    service = VoiceSessionService()
    now = datetime.now(timezone.utc)
    stale_session = VoiceSession(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        status=VoiceSessionStatus.ACTIVE,
        lock_token="lock-token",
        lock_expires_at=now - timedelta(seconds=5),
        last_heartbeat_at=now - timedelta(seconds=95),
        started_at=now - timedelta(minutes=5),
    )
    fresh_session = VoiceSession(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        status=VoiceSessionStatus.ACTIVE,
        lock_token="fresh-lock",
        lock_expires_at=now + timedelta(seconds=60),
        last_heartbeat_at=now - timedelta(seconds=10),
        started_at=now - timedelta(minutes=1),
    )

    db = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = [stale_session]
    db.scalars = AsyncMock(return_value=scalars_result)
    db.flush = AsyncMock()

    abandoned = await service.sweep_abandoned_sessions(db)

    assert abandoned == 1
    assert stale_session.status == VoiceSessionStatus.ABANDONED
    assert stale_session.end_reason == "timeout"
    assert stale_session.ended_at is not None
    assert fresh_session.status == VoiceSessionStatus.ACTIVE


async def _test_assert_lock_activates_created_session() -> None:
    service = VoiceSessionService()
    now = datetime.now(timezone.utc)
    session = VoiceSession(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        status=VoiceSessionStatus.CREATED,
        lock_token="lock-token",
        lock_expires_at=now + timedelta(seconds=60),
        last_heartbeat_at=now,
    )

    db = MagicMock()
    db.get = AsyncMock(return_value=session)
    db.flush = AsyncMock()

    result = await service.assert_lock(db, session.id, "lock-token")

    assert result.status == VoiceSessionStatus.ACTIVE
    assert result.started_at is not None


async def _test_sweep_ignores_already_ended_sessions() -> None:
    service = VoiceSessionService()
    db = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    db.scalars = AsyncMock(return_value=scalars_result)

    abandoned = await service.sweep_abandoned_sessions(db)

    assert abandoned == 0
    db.flush.assert_not_called()


def test_whatsapp_support_url_helper() -> None:
    from app.api.v1.realtime import _whatsapp_support_url

    url = _whatsapp_support_url()
    assert url.startswith("https://wa.me/")
    assert url.replace("https://wa.me/", "").isdigit()


def test_turn_detection_defaults_to_server_vad_threshold_09() -> None:
    from app.services.realtime.openai_realtime_service import OpenaiRealtimeService

    cfg = OpenaiRealtimeService()._turn_detection_config()
    assert cfg["type"] == "server_vad"
    assert cfg["threshold"] == 0.9
    assert cfg["prefix_padding_ms"] == 500
    assert cfg["silence_duration_ms"] == 1200
    assert cfg["interrupt_response"] is True
    assert cfg["create_response"] is True


def main() -> None:
    test_beat_schedule_registers_abandon_sweep()
    test_lock_ttl_is_90_seconds()
    test_whatsapp_support_url_helper()
    test_turn_detection_defaults_to_server_vad_threshold_09()
    asyncio.run(_test_sweep_marks_stale_sessions_abandoned())
    asyncio.run(_test_assert_lock_activates_created_session())
    asyncio.run(_test_sweep_ignores_already_ended_sessions())
    print("verify_voice_abandon_flow: OK")


if __name__ == "__main__":
    main()
