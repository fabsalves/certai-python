"""Lesson completion -- the trigger that ties the cycle together.

When the professor signals that the cohort has studied a lesson (fast path,
no LLM inside the HTTP request):
  1. optionally persist audio + document attachment;
  2. record the raw transcript in a note with ingestion_status=pending;
  3. write progress -> this UNLOCKS the lesson context for students;
  4. enqueue the AI ingestion (extraction + consolidation) in Celery.

The WhatsApp dispatch is chained at the END of the ingestion task: students
only hear from the AI after the material is fully ingested.

Cohort advancement and context unlocking are the same event.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_openai
from app.core.config import settings
from app.core.db_events import enqueue_after_commit
from app.models.assessment import CohortLessonNote
from app.models.track import Lesson
from app.models.cohort import CohortProgress
from app.services.storage import get_storage

CONSOLIDATION_SYSTEM_PROMPT = (
    "You will receive the professor's report about a lesson and, optionally, the "
    "extracted text of a document the professor attached. Produce a JSON object "
    "with keys 'summary', 'unclear_points' and 'knowledge_base', written in "
    "Brazilian Portuguese. 'summary' and 'unclear_points' consolidate the "
    "professor's report. 'knowledge_base' distills the attached document into a "
    "knowledge base for conversations about this lesson: key concepts, "
    "definitions, examples, and points worth exploring with students through "
    "open questions. Be neutral and descriptive -- never judgemental or "
    "moralizing. Use an empty string for 'knowledge_base' when there is no "
    "document. Reply with the JSON only."
)


@dataclass
class StoredFile:
    content: bytes
    filename: str
    content_type: str
    extension: str


async def consolidate_notes(transcript: str, attachment_text: str = "") -> dict[str, str]:
    """The AI turns the professor's report (+ optional attachment) into
    summary + unclear points + lesson knowledge base."""
    empty = {"summary": "", "unclear_points": "", "knowledge_base": ""}
    if not transcript.strip() and not attachment_text.strip():
        return empty

    user_content = f"## Relato do professor\n{transcript.strip() or '(sem relato)'}"
    if attachment_text.strip():
        user_content += f"\n\n## Documento anexado (texto extraído)\n{attachment_text.strip()}"

    client = get_openai()
    resp = await client.chat.completions.create(
        model=settings.ENGINE_MODEL,
        max_tokens=2048,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": CONSOLIDATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    import json

    text = resp.choices[0].message.content or ""
    try:
        return {**empty, **json.loads(text)}
    except json.JSONDecodeError:
        return {**empty, "summary": text}


async def complete_lesson(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    transcript: str,
    *,
    attachment: StoredFile | None = None,
    audio: StoredFile | None = None,
) -> CohortLessonNote:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise ValueError("Aula não encontrada")

    storage = get_storage()
    attachment_key = None
    attachment_filename = None
    attachment_content_type = None
    audio_key = None
    audio_content_type = None

    if attachment is not None:
        attachment_key = (
            f"cohorts/{cohort_id}/lessons/{lesson_id}/attachment/"
            f"{uuid.uuid4()}{attachment.extension}"
        )
        await storage.save(attachment.content, attachment_key, content_type=attachment.content_type)
        attachment_filename = attachment.filename
        attachment_content_type = attachment.content_type

    if audio is not None:
        audio_key = (
            f"cohorts/{cohort_id}/lessons/{lesson_id}/audio/"
            f"{uuid.uuid4()}{audio.extension or '.webm'}"
        )
        await storage.save(audio.content, audio_key, content_type=audio.content_type)
        audio_content_type = audio.content_type

    note = CohortLessonNote(
        cohort_id=cohort_id,
        lesson_id=lesson_id,
        summary="",
        unclear_points="",
        professor_transcript=transcript,
        attachment_storage_key=attachment_key,
        attachment_filename=attachment_filename,
        attachment_content_type=attachment_content_type,
        audio_storage_key=audio_key,
        audio_content_type=audio_content_type,
        ingestion_status="pending",
    )
    db.add(note)

    # Unlock the context: create progress if it does not exist yet.
    exists = await db.scalar(
        select(CohortProgress).where(
            CohortProgress.cohort_id == cohort_id, CohortProgress.lesson_id == lesson_id
        )
    )
    if exists is None:
        next_position = (
            await db.scalar(
                select(func.coalesce(func.max(CohortProgress.global_position), 0)).where(
                    CohortProgress.cohort_id == cohort_id
                )
            )
        ) + 1
        db.add(
            CohortProgress(
                cohort_id=cohort_id, lesson_id=lesson_id, global_position=next_position
            )
        )

    await db.flush()

    from app.services.student_progress_service import StudentProgressService

    await StudentProgressService.on_professor_complete_lesson(db, cohort_id, lesson_id)

    # AI ingestion runs after commit; the WhatsApp dispatch is chained at the
    # end of the ingestion task (never before the ingestion is done).
    from app.workers.tasks import ingest_lesson_completion

    enqueue_after_commit(db, ingest_lesson_completion, str(note.id))

    return note
