"""Persist normalized usage lines (idempotent, never fatal).

Metering must never break a lesson. Every entry point here swallows its own
errors and logs a warning: a lost cost row is an accounting gap, a raised
exception is a student stuck mid-call.

Chat/Groq recording uses a dedicated DB session (awaited, not fire-and-forget)
so the caller's transaction cannot be poisoned and Celery workers do not drop
pending create_task work on recycle. Realtime relay still uses the request
session under SAVEPOINT.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import AiUsageEvent
from app.services.usage.mappers import (
    UsageLine,
    map_groq_transcription_seconds,
    map_openai_chat_completion,
    map_openai_realtime_response,
    map_openai_transcription,
)
from app.services.usage.pricing import estimate_cost_usd

logger = logging.getLogger(__name__)

_CONSTRAINT = "uq_ai_usage_events_provider_event_kind"


@dataclass(frozen=True)
class UsageScope:
    """Who the spend belongs to. Always resolved server-side.

    `cohort_id` is None only for track-wide work (material ingestion), which no
    single cohort owns. Such rows are unattributed overhead, never discarded.
    """

    cohort_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None


# operation -> mapper for provider payloads relayed as raw `usage` dicts.
_MAPPERS = {
    "realtime_response": map_openai_realtime_response,
    "input_transcription": map_openai_transcription,
    "engine": map_openai_chat_completion,
    "humanizer": map_openai_chat_completion,
    "evaluator": map_openai_chat_completion,
    "ingestion": map_openai_chat_completion,
    "summarizer": map_openai_chat_completion,
}


def lines_for(operation: str, usage: dict[str, Any] | None) -> list[UsageLine]:
    mapper = _MAPPERS.get(operation)
    return mapper(usage) if mapper else []


async def ingest_usage_lines(
    db: AsyncSession,
    *,
    scope: UsageScope,
    provider: str,
    model: str,
    operation: str,
    provider_event_id: str,
    lines: list[UsageLine],
    raw: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> int:
    """Insert already-mapped lines. Returns how many new rows were written.

    Uses a SAVEPOINT so a failed insert never aborts the caller's transaction
    (same AsyncSession as engine/evaluator/WhatsApp must stay usable).
    """
    if not lines or not model or not operation or not provider_event_id:
        return 0

    when = occurred_at or datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for line in lines:
        rows.append(
            {
                "id": uuid.uuid4(),
                "cohort_id": scope.cohort_id,
                "student_id": scope.student_id,
                "lesson_id": scope.lesson_id,
                "provider": provider,
                "model": model,
                "operation": operation,
                "cost_kind": line.cost_kind,
                "quantity": line.quantity,
                "unit": line.unit,
                "estimated_cost_usd": estimate_cost_usd(
                    provider=provider,
                    model=model,
                    cost_kind=line.cost_kind,
                    quantity=line.quantity,
                    unit=line.unit,
                ),
                "provider_event_id": provider_event_id,
                "raw": raw,
                "occurred_at": when,
            }
        )

    stmt = (
        insert(AiUsageEvent)
        .values(rows)
        .on_conflict_do_nothing(constraint=_CONSTRAINT)
        .returning(AiUsageEvent.id)
    )
    try:
        async with db.begin_nested():
            result = await db.execute(stmt)
            return len(result.fetchall())
    except Exception:  # noqa: BLE001 -- metering must never break the caller
        logger.warning(
            "Could not ingest usage lines (%s/%s)", operation, provider_event_id, exc_info=True
        )
        return 0


async def ingest_usage_batch(
    db: AsyncSession,
    *,
    scope: UsageScope,
    items: list[dict[str, Any]],
) -> int:
    """Relay entry point: a batch of provider events with raw `usage` payloads.

    Each item: provider, model, operation, provider_event_id, usage, occurred_at.
    Items that do not map to any billable line are skipped silently.
    Never raises — lost rows are an accounting gap only.
    """
    written = 0
    try:
        for item in items:
            provider = str(item.get("provider") or "openai")
            model = str(item.get("model") or "").strip()
            operation = str(item.get("operation") or "").strip()
            event_id = str(item.get("provider_event_id") or "").strip()
            if not model or not operation or not event_id:
                continue

            usage = item.get("usage") if isinstance(item.get("usage"), dict) else None
            lines = _lines_from_item(operation, item, usage)
            if not lines:
                continue

            written += await ingest_usage_lines(
                db,
                scope=scope,
                provider=provider,
                model=model,
                operation=operation,
                provider_event_id=event_id,
                lines=lines,
                raw=usage,
                occurred_at=_parse_time(item.get("occurred_at")),
            )
    except Exception:  # noqa: BLE001
        logger.warning("Could not ingest usage batch", exc_info=True)
    return written


async def record_chat_usage(
    db: AsyncSession,
    *,
    scope: UsageScope,
    operation: str,
    response: Any,
) -> None:
    """Record a Chat Completions response. Never raises.

    `db` is accepted for call-site compatibility; metering uses its own session
    so a failure cannot abort the caller's transaction. Persist is awaited so
    Celery's run_until_complete does not drop pending work on task end.
    """
    _ = db  # dedicated session — see _persist_lines_isolated
    try:
        usage = _usage_dict(getattr(response, "usage", None))
        event_id = str(getattr(response, "id", "") or "").strip()
        model = str(getattr(response, "model", "") or "").strip()
        if not usage or not event_id or not model:
            return
        lines = map_openai_chat_completion(usage)
        if not lines:
            return
        await _persist_lines_isolated(
            scope=scope,
            provider="openai",
            model=model,
            operation=operation,
            provider_event_id=f"{event_id}:{operation}",
            lines=lines,
            raw=usage,
        )
    except Exception:  # noqa: BLE001 -- metering must never break the caller
        logger.warning("Could not record %s usage", operation, exc_info=True)


async def record_groq_transcription(
    db: AsyncSession,
    *,
    scope: UsageScope,
    model: str,
    provider_event_id: str,
    seconds: float | Decimal | None,
) -> None:
    """Record Groq/Whisper transcription. Never raises; persist is awaited."""
    _ = db
    try:
        lines = map_groq_transcription_seconds(seconds)
        if not lines:
            return
        await _persist_lines_isolated(
            scope=scope,
            provider="groq",
            model=model,
            operation="transcription",
            provider_event_id=provider_event_id,
            lines=lines,
            raw={"seconds": float(seconds or 0)},
        )
    except Exception:  # noqa: BLE001
        logger.warning("Could not record transcription usage", exc_info=True)


async def _persist_lines_isolated(
    *,
    scope: UsageScope,
    provider: str,
    model: str,
    operation: str,
    provider_event_id: str,
    lines: list[UsageLine],
    raw: dict[str, Any] | None,
) -> None:
    from app.core.database import SessionLocal

    try:
        async with SessionLocal() as session:
            await ingest_usage_lines(
                session,
                scope=scope,
                provider=provider,
                model=model,
                operation=operation,
                provider_event_id=provider_event_id,
                lines=lines,
                raw=raw,
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.warning(
            "Isolated usage persist failed (%s/%s)",
            operation,
            provider_event_id,
            exc_info=True,
        )


def _lines_from_item(
    operation: str, item: dict[str, Any], usage: dict[str, Any] | None
) -> list[UsageLine]:
    """Pre-mapped `lines` win over the raw payload, for callers that map upstream."""
    if item.get("lines"):
        out: list[UsageLine] = []
        for row in item["lines"]:
            kind = str(row.get("cost_kind") or "")
            try:
                qty = Decimal(str(row.get("quantity") or 0))
            except Exception:  # noqa: BLE001
                continue
            if kind and qty > 0:
                out.append(
                    UsageLine(
                        cost_kind=kind,
                        quantity=qty,
                        unit=str(row.get("unit") or "tokens"),
                    )
                )
        return out
    return lines_for(operation, usage)


def _usage_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    for attr in ("model_dump", "to_dict", "dict"):
        method = getattr(usage, attr, None)
        if callable(method):
            try:
                dumped = method()
                if isinstance(dumped, dict):
                    return dumped
            except Exception:  # noqa: BLE001
                continue
    return None


def _parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None
