"""Async tasks.

Celery runs sync; the rest of the app is async. The bridge is `run_async()` in
async_runner.py (one persistent loop per worker process). Each task opens its own
DB session (it does not share the request's).
"""

import logging
from uuid import UUID

from sqlalchemy import select

from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def transcribe_audio(self, audio_path: str, conversation_id: str) -> dict:
    """Transcribe audio (Groq/Whisper) and attach the text to the conversation."""
    try:
        return run_async(_transcribe_audio(audio_path, UUID(conversation_id)))
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def plan_dispatch(self, cohort_id: str, lesson_id: str) -> dict:
    """After a lesson is completed, dispatch WhatsApp invites to enrolled students."""
    try:
        return run_async(_plan_dispatch(UUID(cohort_id), UUID(lesson_id)))
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_whatsapp_inbound(self, conversation_id: str, task_id: str) -> dict:
    """Process debounced inbound WhatsApp message and reply via Cinndi."""
    try:
        return run_async(_process_whatsapp_inbound(UUID(conversation_id), task_id))
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def ingest_lesson_completion(self, note_id: str) -> dict:
    """AI ingestion of the lesson report (transcript + attachment). On success,
    chains the WhatsApp dispatch; students are only invited after ingestion."""
    try:
        return run_async(_ingest_lesson_completion(UUID(note_id)))
    except Exception as exc:  # noqa: BLE001
        # retry(exc=...) re-raises exc itself once retries are exhausted, so the
        # failed state must be recorded before delegating to Celery.
        if self.request.retries >= self.max_retries:
            run_async(_mark_lesson_ingestion_failed(UUID(note_id)))
            raise
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def ingest_track_material(self, track_id: str) -> dict:
    """AI ingestion of the track material file into a macro track guide."""
    try:
        return run_async(_ingest_track_material(UUID(track_id)))
    except Exception as exc:  # noqa: BLE001
        if self.request.retries >= self.max_retries:
            run_async(_mark_track_ingestion_failed(UUID(track_id)))
            raise
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def evaluate_cohort_gaps(self, cohort_id: str) -> dict:
    """An external AI reads the cohort's micro-scores and points out gaps."""
    return run_async(_evaluate_gaps(UUID(cohort_id)))


@celery_app.task
def sweep_evaluations() -> dict:
    """Scheduled job (Beat): triggers evaluation for every active cohort."""
    return run_async(_sweep_evaluations())


@celery_app.task
def sweep_abandoned_voice_sessions() -> dict:
    """Scheduled job (Beat): marca sessões de voz sem heartbeat há 90s como abandoned."""
    return run_async(_sweep_abandoned_voice_sessions())


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
    from app.core.database import SessionLocal
    from app.services.whatsapp.dispatch_service import dispatch_lesson_invites

    async with SessionLocal() as db:
        return await dispatch_lesson_invites(db, cohort_id, lesson_id)


async def _ingest_lesson_completion(note_id: UUID) -> dict:
    from app.core.database import SessionLocal
    from app.services.ingestion.lesson_note_ingestion_service import ingest_lesson_note

    async with SessionLocal() as db:
        note = await ingest_lesson_note(db, note_id)
        cohort_id, lesson_id = str(note.cohort_id), str(note.lesson_id)
        await db.commit()

    # Dispatch only on the transition to done, after the ingestion is committed.
    plan_dispatch.delay(cohort_id, lesson_id)
    return {"note_id": str(note_id), "status": "done", "dispatch": "enqueued"}


async def _mark_lesson_ingestion_failed(note_id: UUID) -> None:
    from app.core.database import SessionLocal
    from app.services.ingestion.lesson_note_ingestion_service import mark_lesson_note_failed

    async with SessionLocal() as db:
        await mark_lesson_note_failed(db, note_id)
        await db.commit()


async def _ingest_track_material(track_id: UUID) -> dict:
    from app.core.database import SessionLocal
    from app.services.ingestion.track_material_service import ingest_track_material as run_ingestion

    async with SessionLocal() as db:
        track = await run_ingestion(db, track_id)
        status = track.material_ingestion_status
        await db.commit()
    return {"track_id": str(track_id), "status": status}


async def _mark_track_ingestion_failed(track_id: UUID) -> None:
    from app.core.database import SessionLocal
    from app.services.ingestion.track_material_service import mark_track_material_failed

    async with SessionLocal() as db:
        await mark_track_material_failed(db, track_id)
        await db.commit()


async def _process_whatsapp_inbound(conversation_id: UUID, task_id: str) -> dict:
    from app.core.database import SessionLocal
    from app.models.conversation import Author, Conversation, Message, MessageSource
    from app.models.user import User
    from app.services.cinndi.outbound import CinndiOutboundError, send_text_message
    from app.services.conversation_service import generate_lesson_reply
    from app.services.whatsapp.debounce import clear_debounce, is_active_task

    if not await is_active_task(conversation_id, task_id):
        return {"status": "stale", "conversation_id": str(conversation_id)}

    async with SessionLocal() as db:
        conversation = await db.get(Conversation, conversation_id)
        if conversation is None or conversation.lesson_id is None:
            await clear_debounce(conversation_id)
            return {"status": "missing_conversation"}

        from app.services.student_progress_service import StudentProgressService

        if not await StudentProgressService.is_lesson_interactive_for(
            db,
            conversation.cohort_id,
            conversation.user_id,
            conversation.lesson_id,
        ):
            await clear_debounce(conversation_id)
            return {"status": "lesson_closed"}

        student = await db.get(User, conversation.user_id)
        if student is None or not student.whatsapp:
            await clear_debounce(conversation_id)
            return {"status": "missing_whatsapp"}

        try:
            final = await generate_lesson_reply(
                db,
                conversation,
                conversation.cohort_id,
                conversation.lesson_id,
                conversation.user_id,
                entry_source=MessageSource.WHATSAPP_TEXT,
            )
            provider_id = send_text_message(to_phone=student.whatsapp, body=final)

            last_msg = await db.scalar(
                select(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.author == Author.AGENT,
                )
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            if last_msg is not None:
                last_msg.provider_message_id = provider_id
                last_msg.delivery_status = "sent"
            await db.commit()
        except CinndiOutboundError as exc:
            await db.rollback()
            logger.warning("whatsapp reply failed conv=%s: %s", conversation_id, exc)
            await clear_debounce(conversation_id)
            return {"status": "send_failed", "error": str(exc)}
        except Exception:
            await db.rollback()
            raise

    await clear_debounce(conversation_id)
    return {"status": "ok", "conversation_id": str(conversation_id)}


async def _evaluate_gaps(cohort_id: UUID) -> dict:
    from app.ai.client import get_openai
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
    client = get_openai()
    resp = await client.chat.completions.create(
        model=settings.EVALUATOR_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the external evaluator. From the micro-scores, point out "
                    "knowledge gaps per competency and per student. Do not compute a single "
                    "average. Write the report in Brazilian Portuguese."
                ),
            },
            {"role": "user", "content": str(data)},
        ],
    )
    report = resp.choices[0].message.content or ""
    return {"cohort_id": str(cohort_id), "report": report}


async def _sweep_evaluations() -> dict:
    from app.core.database import SessionLocal
    from app.models.cohort import Cohort

    async with SessionLocal() as db:
        cohorts = (await db.execute(select(Cohort.id))).scalars().all()
    for cid in cohorts:
        evaluate_cohort_gaps.delay(str(cid))
    return {"cohorts_enqueued": len(cohorts)}


async def _sweep_abandoned_voice_sessions() -> dict:
    from app.core.database import SessionLocal
    from app.services.realtime.voice_session_service import VoiceSessionService

    async with SessionLocal() as db:
        abandoned = await VoiceSessionService().sweep_abandoned_sessions(db)
        await db.commit()
    return {"abandoned": abandoned}
