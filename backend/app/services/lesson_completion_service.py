"""Lesson completion -- the trigger that ties the cycle together.

When the professor signals that the cohort has studied a lesson:
  1. record the audio transcript;
  2. the AI consolidates notes (summary + unclear points) per cohort+lesson;
  3. write progress -> this UNLOCKS the lesson context for students;
  4. enqueue dispatch planning.

Cohort advancement and context unlocking are the same event.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_anthropic
from app.core.config import settings
from app.models.assessment import CohortLessonNote
from app.models.track import Lesson
from app.models.cohort import CohortProgress


async def consolidate_notes(transcript: str) -> dict[str, str]:
    """The AI turns the professor's report into summary + unclear points."""
    if not transcript.strip():
        return {"summary": "", "unclear_points": ""}
    client = get_anthropic()
    resp = await client.messages.create(
        model=settings.ENGINE_MODEL,
        max_tokens=512,
        system=(
            "From the professor's report about the lesson, produce a JSON object "
            "with keys 'summary' and 'unclear_points', written in Brazilian "
            "Portuguese. Reply with the JSON only."
        ),
        messages=[{"role": "user", "content": transcript}],
    )
    import json

    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"summary": text, "unclear_points": ""}


async def complete_lesson(
    db: AsyncSession, cohort_id: uuid.UUID, lesson_id: uuid.UUID, transcript: str
) -> CohortLessonNote:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise ValueError("Aula não encontrada")

    consolidated = await consolidate_notes(transcript)

    note = CohortLessonNote(
        cohort_id=cohort_id,
        lesson_id=lesson_id,
        summary=consolidated.get("summary", ""),
        unclear_points=consolidated.get("unclear_points", ""),
        professor_transcript=transcript,
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

    # Dispatch planning runs in the background (does not block the professor).
    from app.workers.tasks import plan_dispatch

    plan_dispatch.delay(str(cohort_id), str(lesson_id))

    return note
