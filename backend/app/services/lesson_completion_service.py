"""Lesson completion -- the trigger that ties the cycle together.

When the professor signals that the cohort has studied a lesson:
  1. optionally persist audio + document attachment (compliance);
  2. record the audio transcript;
  3. the AI consolidates notes (summary + unclear points) per cohort+lesson;
  4. write progress -> this UNLOCKS the lesson context for students;
  5. enqueue dispatch planning.

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


@dataclass
class StoredFile:
    content: bytes
    filename: str
    content_type: str
    extension: str


async def consolidate_notes(transcript: str) -> dict[str, str]:
    """The AI turns the professor's report into summary + unclear points."""
    if not transcript.strip():
        return {"summary": "", "unclear_points": ""}
    client = get_openai()
    resp = await client.chat.completions.create(
        model=settings.ENGINE_MODEL,
        max_tokens=512,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "From the professor's report about the lesson, produce a JSON object "
                    "with keys 'summary' and 'unclear_points', written in Brazilian "
                    "Portuguese. Reply with the JSON only."
                ),
            },
            {"role": "user", "content": transcript},
        ],
    )
    import json

    text = resp.choices[0].message.content or ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"summary": text, "unclear_points": ""}


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

    consolidated = await consolidate_notes(transcript)

    note = CohortLessonNote(
        cohort_id=cohort_id,
        lesson_id=lesson_id,
        summary=consolidated.get("summary", ""),
        unclear_points=consolidated.get("unclear_points", ""),
        professor_transcript=transcript,
        attachment_storage_key=attachment_key,
        attachment_filename=attachment_filename,
        attachment_content_type=attachment_content_type,
        audio_storage_key=audio_key,
        audio_content_type=audio_content_type,
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

    # Dispatch runs after commit so progress is visible to the worker.
    from app.workers.tasks import plan_dispatch

    enqueue_after_commit(db, plan_dispatch, str(cohort_id), str(lesson_id))

    return note
