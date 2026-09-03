"""Lesson completion -- the trigger that ties the cycle together.

When a professor signals that their class has studied a lesson (fast path,
no LLM inside the HTTP request):
  1. optionally persist audio + document attachment;
  2. record the raw transcript in a note with ingestion_status=pending;
  3. write progress -> this UNLOCKS the lesson context for that class;
  4. enqueue the AI ingestion (extraction + consolidation) in Celery.

The WhatsApp dispatch is chained at the END of the ingestion task: students
only hear from the AI after the material is fully ingested.

Everything here is scoped to the professor's own class: a module taught by two
professors produces two reports, two unlocks and two dispatches.

Class advancement and context unlocking are the same event.
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
from app.models.cohort import CohortModuleProfessor, CohortProgress
from app.schemas import CoverageSegmentIn
from app.services import coverage_service
from app.services.storage import get_storage
from app.services.usage import UsageScope, record_chat_usage

CONSOLIDATION_SYSTEM_PROMPT = (
    "You will receive the professor's report about a lesson and, optionally, the "
    "extracted text of a document the professor attached and the confirmed "
    "coverage of the session. Produce a JSON object "
    "with keys 'summary', 'unclear_points' and 'knowledge_base', written in "
    "Brazilian Portuguese. 'summary' and 'unclear_points' consolidate the "
    "professor's report. 'knowledge_base' distills the attached document into a "
    "knowledge base for conversations about this lesson: key concepts, "
    "definitions, examples, and points worth exploring with students through "
    "open questions. Be neutral and descriptive -- never judgemental or "
    "moralizing. Use an empty string for 'knowledge_base' when there is no "
    "document.\n\n"
    "When a coverage section is present, it is the EXHAUSTIVE boundary of this "
    "consolidation: only what it declares as ministered may appear in the three "
    "fields. If the report mentions anything the coverage does not declare -- "
    "content it marks as not ministered, or content of a lesson it does not list "
    "at all -- leave that out entirely, including any remark that it happened. "
    "Either those students did not receive it, or it belongs to another "
    "professor's class; and this note is what the AI will discuss with them, so "
    "a passing mention already puts it in front of the student. When the coverage "
    "does list a neighbouring lesson, write what it says was taught of it, never "
    "that lesson's full material.\n\n"
    "Reply with the JSON only."
)


@dataclass
class StoredFile:
    content: bytes
    filename: str
    content_type: str
    extension: str


async def consolidate_notes(
    transcript: str,
    attachment_text: str = "",
    *,
    coverage_block: str = "",
    db: AsyncSession | None = None,
    scope: UsageScope | None = None,
) -> dict[str, str]:
    """The AI turns the professor's report (+ optional attachment) into
    summary + unclear points + lesson knowledge base.

    `coverage_block` is the session's confirmed coverage. When present it bounds
    the consolidation to what was actually ministered -- which is what keeps a
    pendency out of the students' context, and keeps content taught ahead from
    landing in this lesson's knowledge base.
    """
    empty = {"summary": "", "unclear_points": "", "knowledge_base": ""}
    if not transcript.strip() and not attachment_text.strip():
        return empty

    user_content = f"## Relato do professor\n{transcript.strip() or '(sem relato)'}"
    if coverage_block.strip():
        user_content += (
            f"\n\n## Cobertura confirmada desta sessão\n{coverage_block.strip()}"
        )
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
    if db is not None and scope is not None:
        await record_chat_usage(db, scope=scope, operation="ingestion", response=resp)

    import json

    text = resp.choices[0].message.content or ""
    try:
        return {**empty, **json.loads(text)}
    except json.JSONDecodeError:
        return {**empty, "summary": text}


AUDIO_SOURCES = frozenset({"recording", "file"})


def normalize_audio_source(value: str | None, *, has_audio: bool) -> str | None:
    """Persist only known origins; omit when there is no audio file."""
    if not has_audio:
        return None
    source = (value or "").strip().lower()
    if source in AUDIO_SOURCES:
        return source
    return None


async def complete_lesson(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    transcript: str,
    *,
    module_professor_id: uuid.UUID,
    attachment: StoredFile | None = None,
    audio: StoredFile | None = None,
    audio_source: str | None = None,
    coverage: list[CoverageSegmentIn] | None = None,
) -> CohortLessonNote:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise ValueError("Aula não encontrada")

    storage = get_storage()
    attachment_key = None
    attachment_filename = None
    attachment_content_type = None
    audio_key = None
    audio_filename = None
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
        audio_filename = audio.filename
        audio_content_type = audio.content_type

    note = CohortLessonNote(
        cohort_id=cohort_id,
        lesson_id=lesson_id,
        module_professor_id=module_professor_id,
        summary="",
        unclear_points="",
        professor_transcript=transcript,
        attachment_storage_key=attachment_key,
        attachment_filename=attachment_filename,
        attachment_content_type=attachment_content_type,
        audio_storage_key=audio_key,
        audio_filename=audio_filename,
        audio_content_type=audio_content_type,
        audio_source=normalize_audio_source(audio_source, has_audio=audio is not None),
        ingestion_status="pending",
    )
    db.add(note)

    # Unlock the context for this class: create progress if it does not exist yet.
    exists = await db.scalar(
        select(CohortProgress).where(
            CohortProgress.cohort_id == cohort_id,
            CohortProgress.lesson_id == lesson_id,
            CohortProgress.module_professor_id == module_professor_id,
        )
    )
    if exists is None:
        next_position = (
            await db.scalar(
                select(func.coalesce(func.max(CohortProgress.global_position), 0)).where(
                    CohortProgress.cohort_id == cohort_id,
                    CohortProgress.module_professor_id == module_professor_id,
                )
            )
        ) + 1
        db.add(
            CohortProgress(
                cohort_id=cohort_id,
                lesson_id=lesson_id,
                module_professor_id=module_professor_id,
                global_position=next_position,
            )
        )

    await db.flush()

    module_class = await db.get(CohortModuleProfessor, module_professor_id)
    if module_class is None:
        raise ValueError("Turma do professor não encontrada")

    # The session declares what it actually covered. Without an informed
    # coverage this writes the happy-path row (anchor, full) -- so a client that
    # knows nothing about coverage behaves exactly as before.
    window = await coverage_service.candidate_window(
        db, cohort_id, lesson_id, module_professor_id=module_professor_id
    )
    positions = {item.id: index for index, item in enumerate(window)}
    await coverage_service.persist_coverage(
        db,
        note=note,
        segments=coverage or [coverage_service.default_segment(lesson_id)],
        allowed_positions=positions,
        anchor_position=positions.get(lesson_id, 0),
        owners=await coverage_service.owning_class_ids(
            db, cohort_id, module_class, window
        ),
    )

    from app.services.cohort import ModuleClassService
    from app.services.student_progress_service import StudentProgressService

    student_ids = await ModuleClassService.student_ids_of(db, module_class)
    await StudentProgressService.on_professor_complete_lesson(
        db, cohort_id, lesson_id, student_ids
    )

    # AI ingestion runs after commit; the WhatsApp dispatch is chained at the
    # end of the ingestion task (never before the ingestion is done).
    from app.workers.tasks import ingest_lesson_completion

    enqueue_after_commit(db, ingest_lesson_completion, str(note.id))

    return note
