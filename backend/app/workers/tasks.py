"""Async tasks.

Celery runs sync; the rest of the app is async. The bridge is `run_async()`, which
runs the coroutine in the task's own event loop. Each task opens its own DB session
(it does not share the request's).
"""

import asyncio
from typing import Any
from uuid import UUID

from app.workers.celery_app import celery_app


def run_async(coro: Any) -> Any:
    return asyncio.run(coro)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def transcribe_audio(self, audio_path: str, conversation_id: str) -> dict:
    """Transcribe audio (Groq/Whisper) and attach the text to the conversation."""
    try:
        return run_async(_transcribe_audio(audio_path, UUID(conversation_id)))
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def plan_dispatch(self, cohort_id: str, lesson_id: str) -> dict:
    """After a lesson is completed, the AI plans the dispatch to students."""
    return run_async(_plan_dispatch(UUID(cohort_id), UUID(lesson_id)))


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def evaluate_cohort_gaps(self, cohort_id: str) -> dict:
    """An external AI reads the cohort's micro-scores and points out gaps."""
    return run_async(_evaluate_gaps(UUID(cohort_id)))


@celery_app.task
def sweep_evaluations() -> dict:
    """Scheduled job (Beat): triggers evaluation for every active cohort."""
    return run_async(_sweep_evaluations())


# --- async implementations ---

async def _transcribe_audio(audio_path: str, conversation_id: UUID) -> dict:
    from groq import AsyncGroq

    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models.conversation import Author, Message

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    with open(audio_path, "rb") as f:
        resp = await client.audio.transcriptions.create(
            file=(audio_path, f.read()), model=settings.GROQ_TRANSCRIBE_MODEL
        )
    text = resp.text

    async with SessionLocal() as db:
        db.add(Message(conversation_id=conversation_id, author=Author.PROFESSOR, content=text))
        await db.commit()
    return {"conversation_id": str(conversation_id), "chars": len(text)}


async def _plan_dispatch(cohort_id: UUID, lesson_id: UUID) -> dict:
    # The AI decides what to send, to whom and when. Integration point stub:
    # the engine with planning scope + the notification queue would go here.
    return {"cohort_id": str(cohort_id), "lesson_id": str(lesson_id), "status": "planned"}


async def _evaluate_gaps(cohort_id: UUID) -> dict:
    from sqlalchemy import select

    from app.ai.client import get_anthropic
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models.assessment import MicroScore

    async with SessionLocal() as db:
        rows = (
            await db.execute(select(MicroScore).where(MicroScore.cohort_id == cohort_id))
        ).scalars().all()

    data = [
        {"competency": r.competency, "level": r.level.value, "student": str(r.student_id)}
        for r in rows
    ]
    client = get_anthropic()
    resp = await client.messages.create(
        model=settings.EVALUATOR_MODEL,
        max_tokens=1024,
        system=(
            "You are the external evaluator. From the micro-scores, point out "
            "knowledge gaps per competency and per student. Do not compute a single "
            "average. Write the report in Brazilian Portuguese."
        ),
        messages=[{"role": "user", "content": str(data)}],
    )
    report = "".join(b.text for b in resp.content if b.type == "text")
    return {"cohort_id": str(cohort_id), "report": report}


async def _sweep_evaluations() -> dict:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.cohort import Cohort

    async with SessionLocal() as db:
        cohorts = (await db.execute(select(Cohort.id))).scalars().all()
    for cid in cohorts:
        evaluate_cohort_gaps.delay(str(cid))
    return {"cohorts_enqueued": len(cohorts)}
