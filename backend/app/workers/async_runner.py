"""Persistent asyncio loop for Celery worker processes.

Celery tasks are sync; the app is async. Using asyncio.run() per task closes the
loop and leaves global async clients (SQLAlchemy engine, Redis) bound to a dead
loop. This module keeps one loop per forked worker process.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, TypeVar

from celery.signals import worker_process_init, worker_process_shutdown

logger = logging.getLogger(__name__)

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None


async def _prepare_async_resources() -> None:
    """Drop inherited connections after prefork and bind clients to this loop."""
    from redis.asyncio import from_url

    from app.core import redis_client as redis_module
    from app.core.config import settings
    from app.core.database import engine

    await engine.dispose()

    try:
        await redis_module.redis_client.aclose()
    except Exception:  # noqa: BLE001
        pass

    redis_module.redis_client = from_url(
        str(settings.REDIS_URL),
        encoding="utf-8",
        decode_responses=True,
    )


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    return _ensure_loop().run_until_complete(coro)


@worker_process_init.connect
def _init_worker_process(**kwargs: Any) -> None:
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_until_complete(_prepare_async_resources())
    logger.debug("celery worker async loop ready pid=%s", kwargs.get("pid"))


@worker_process_shutdown.connect
def _shutdown_worker_process(**kwargs: Any) -> None:
    global _loop
    if _loop is None or _loop.is_closed():
        return

    async def _cleanup() -> None:
        from app.core import redis_client as redis_module
        from app.core.database import engine

        await engine.dispose()
        try:
            await redis_module.redis_client.aclose()
        except Exception:  # noqa: BLE001
            pass

    try:
        _loop.run_until_complete(_cleanup())
    finally:
        _loop.close()
        _loop = None
