"""Debounce inbound WhatsApp turns per conversation (Redis)."""

from __future__ import annotations

import json
import logging
import uuid

from app.core.config import settings
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

KEY_PREFIX = "certai:whatsapp_debounce"
TTL_SECONDS = 120


def _key(conversation_id: str) -> str:
    return f"{KEY_PREFIX}:{conversation_id}"


async def schedule_inbound_processing(conversation_id: uuid.UUID) -> str:
    """Reset quiet-period timer and enqueue processing."""
    from app.workers.tasks import process_whatsapp_inbound

    conv_id = str(conversation_id)
    key = _key(conv_id)
    previous_task_id: str | None = None

    raw = await redis_client.get(key)
    if raw:
        try:
            state = json.loads(raw)
            previous_task_id = str(state.get("task_id") or "") or None
        except json.JSONDecodeError:
            pass

    if previous_task_id:
        try:
            from app.workers.celery_app import celery_app

            celery_app.control.revoke(previous_task_id, terminate=False)
        except Exception as exc:  # noqa: BLE001
            logger.debug("debounce revoke skipped: %s", exc)

    task_id = str(uuid.uuid4())
    await redis_client.setex(
        key,
        TTL_SECONDS,
        json.dumps({"task_id": task_id}),
    )
    process_whatsapp_inbound.apply_async(
        args=(conv_id, task_id),
        countdown=settings.INBOUND_DEBOUNCE_SECONDS,
        task_id=task_id,
    )
    return task_id


async def is_active_task(conversation_id: uuid.UUID, task_id: str) -> bool:
    raw = await redis_client.get(_key(str(conversation_id)))
    if not raw:
        return False
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return str(state.get("task_id") or "") == task_id


async def clear_debounce(conversation_id: uuid.UUID) -> None:
    await redis_client.delete(_key(str(conversation_id)))
