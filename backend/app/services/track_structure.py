import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Lesson, Module


def normalize_title(title: str) -> str:
    return title.strip().casefold()


async def ensure_unique_module_title(
    db: AsyncSession,
    track_id: uuid.UUID,
    title: str,
    *,
    exclude_module_id: uuid.UUID | None = None,
) -> str:
    cleaned = title.strip()
    normalized = normalize_title(cleaned)
    stmt = select(Module.id).where(
        Module.track_id == track_id,
        func.lower(func.trim(Module.title)) == normalized,
    )
    if exclude_module_id is not None:
        stmt = stmt.where(Module.id != exclude_module_id)
    if await db.scalar(stmt):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Já existe um módulo com este nome nesta trilha.",
        )
    return cleaned


async def ensure_unique_lesson_title(
    db: AsyncSession,
    module_id: uuid.UUID,
    title: str,
    *,
    exclude_lesson_id: uuid.UUID | None = None,
) -> str:
    cleaned = title.strip()
    normalized = normalize_title(cleaned)
    stmt = select(Lesson.id).where(
        Lesson.module_id == module_id,
        func.lower(func.trim(Lesson.title)) == normalized,
    )
    if exclude_lesson_id is not None:
        stmt = stmt.where(Lesson.id != exclude_lesson_id)
    if await db.scalar(stmt):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Já existe uma aula com este título neste módulo.",
        )
    return cleaned
