"""Database lifecycle helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession


def enqueue_after_commit(
    db: AsyncSession,
    task: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """Enqueue a Celery task only after the current transaction commits."""
    sync_session = db.sync_session

    @event.listens_for(sync_session, "after_commit", once=True)
    def _on_commit(_session: object) -> None:
        task.delay(*args, **kwargs)
