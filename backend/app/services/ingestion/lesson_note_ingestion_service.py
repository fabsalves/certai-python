"""Ingestion of the lesson-completion report (transcript + optional attachment).

Runs inside the Celery worker. The WhatsApp dispatch is chained AFTER the
ingestion transitions to done -- never before. This makes "students only hear
from the AI once it has ingested the material" a structural guarantee.
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import CohortLessonNote
from app.services.ingestion import (
    INGESTION_DONE,
    INGESTION_FAILED,
    INGESTION_PROCESSING,
)
from app.services.ingestion.extraction import UnsupportedFormatError, extract_text
from app.services.lesson_completion_service import consolidate_notes
from app.services.storage import get_storage

logger = logging.getLogger(__name__)


async def ingest_lesson_note(db: AsyncSession, note_id: uuid.UUID) -> CohortLessonNote:
    """Extract the attachment text, consolidate everything via LLM, mark done."""
    note = await db.get(CohortLessonNote, note_id)
    if note is None:
        raise ValueError("Relato não encontrado")

    note.ingestion_status = INGESTION_PROCESSING
    await db.flush()

    attachment_text = ""
    if note.attachment_storage_key:
        content = await get_storage().open(note.attachment_storage_key)
        extension = Path(note.attachment_filename or note.attachment_storage_key).suffix
        try:
            attachment_text = extract_text(content, extension)
        except UnsupportedFormatError:
            logger.warning(
                "lesson note %s: attachment without text extractor (%s)", note_id, extension
            )

    consolidated = await consolidate_notes(note.professor_transcript, attachment_text)

    note.attachment_extracted_text = attachment_text
    note.summary = consolidated.get("summary", "")
    note.unclear_points = consolidated.get("unclear_points", "")
    note.attachment_knowledge_base = consolidated.get("knowledge_base", "")
    note.ingestion_status = INGESTION_DONE
    await db.flush()
    return note


async def mark_lesson_note_failed(db: AsyncSession, note_id: uuid.UUID) -> None:
    note = await db.get(CohortLessonNote, note_id)
    if note is not None:
        note.ingestion_status = INGESTION_FAILED
        await db.flush()
