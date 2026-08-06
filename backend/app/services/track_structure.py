import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.track import Lesson, Module, Track


def normalize_title(title: str) -> str:
    return title.strip().casefold()


async def ordered_active_lessons(
    db: AsyncSession, track_id: uuid.UUID
) -> list[Lesson]:
    """Active lessons of a track in teaching order. The one sequence everything
    else (progression, completion gate, advancement) reads."""
    track = await db.scalar(
        select(Track)
        .where(Track.id == track_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    if track is None:
        return []

    lessons: list[Lesson] = []
    for module in sorted(track.modules, key=lambda item: item.position):
        if not module.is_active:
            continue
        for lesson in sorted(module.lessons, key=lambda item: item.position):
            if lesson.is_active:
                lessons.append(lesson)
    return lessons


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
