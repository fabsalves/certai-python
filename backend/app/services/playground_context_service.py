"""Assemble the AI context snapshot shown in the admin playground."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.context_builder import ContextBuilder
from app.models.assessment import CohortLessonNote
from app.models.cohort import Cohort, CohortProgress
from app.models.track import Lesson, Module, Track
from app.services.ingestion import INGESTION_DONE


async def build_playground_context(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> dict:
    """Return the structured bundle the Lira receives plus ingestion metadata."""
    bundle = await ContextBuilder(db).build_lesson(cohort_id, lesson_id)

    cohort = await db.get(Cohort, cohort_id)
    track = await db.scalar(
        select(Track)
        .where(Track.id == cohort.track_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    if track is None:
        raise ValueError("Trilha não encontrada")

    unlocked_ids = set(
        (
            await db.execute(
                select(CohortProgress.lesson_id).where(CohortProgress.cohort_id == cohort_id)
            )
        ).scalars().all()
    )

    lesson_titles: dict[uuid.UUID, str] = {}
    for module in track.modules:
        for lesson in module.lessons:
            lesson_titles[lesson.id] = lesson.title

    notes_by_lesson: dict[uuid.UUID, CohortLessonNote] = {}
    if unlocked_ids:
        note_rows = (
            await db.execute(
                select(CohortLessonNote)
                .where(
                    CohortLessonNote.cohort_id == cohort_id,
                    CohortLessonNote.lesson_id.in_(unlocked_ids),
                )
                .order_by(CohortLessonNote.created_at.desc())
            )
        ).scalars().all()
        for note in note_rows:
            if note.lesson_id not in notes_by_lesson:
                notes_by_lesson[note.lesson_id] = note

    lesson_notes = []
    for lid in sorted(unlocked_ids, key=lambda x: str(x)):
        note = notes_by_lesson.get(lid)
        if note is not None:
            lesson_notes.append(
                {
                    "lesson_id": str(lid),
                    "lesson_title": lesson_titles.get(lid, ""),
                    "ingestion_status": note.ingestion_status,
                    "summary": note.summary,
                    "unclear_points": note.unclear_points,
                    "knowledge_base": note.attachment_knowledge_base,
                    "has_attachment": bool(note.attachment_storage_key),
                    "attachment_filename": note.attachment_filename,
                    "in_ai_bundle": note.ingestion_status == INGESTION_DONE,
                }
            )
        else:
            lesson_notes.append(
                {
                    "lesson_id": str(lid),
                    "lesson_title": lesson_titles.get(lid, ""),
                    "ingestion_status": None,
                    "summary": "",
                    "unclear_points": "",
                    "knowledge_base": "",
                    "has_attachment": False,
                    "attachment_filename": None,
                    "in_ai_bundle": False,
                }
            )

    track_guide_in_bundle = bundle.track_guide
    return {
        "scope": bundle.scope,
        "current_position": bundle.current_position,
        "track_map": bundle.track_map,
        "unlocked_content": bundle.unlocked_content,
        "cohort_notes_in_bundle": bundle.cohort_notes,
        "track_guide_in_bundle": track_guide_in_bundle,
        "system_blocks": bundle.to_system_blocks(),
        "track_material": {
            "filename": track.material_filename,
            "ingestion_status": track.material_ingestion_status,
            "guide": track.material_guide if track.material_ingestion_status == INGESTION_DONE else "",
            "in_ai_bundle": track.material_ingestion_status == INGESTION_DONE and bool(
                track.material_guide.strip()
            ),
        },
        "lesson_notes": lesson_notes,
    }
