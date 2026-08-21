"""Demo AI usage rows for the Custos screen (no live API calls).

Spreads realistic token volumes across turma/aluno/aula and every `operation`
the app meters. Idempotent: skips if any row already exists.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from random import Random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cohort import Cohort
from app.models.track import Lesson, Module, Track
from app.models.usage import AiUsageEvent
from app.models.user import User
from app.services.usage.pricing import estimate_cost_usd

RNG = Random(42)

# Models actually reported by the API in production paths.
REALTIME_MODEL = "gpt-realtime-2"
TRANSCRIBE_MODEL = "gpt-4o-mini-transcribe"
ENGINE_MODEL = "gpt-4o"
HUMANIZER_MODEL = "gpt-4o-mini-2024-07-18"
GROQ_WHISPER = "whisper-large-v3"


def _usd(
    provider: str,
    model: str,
    cost_kind: str,
    quantity: Decimal,
    *,
    unit: str = "tokens",
) -> Decimal | None:
    return estimate_cost_usd(
        provider=provider,
        model=model,
        cost_kind=cost_kind,
        quantity=quantity,
        unit=unit,
    )


def _line(
    *,
    cohort_id: uuid.UUID | None,
    student_id: uuid.UUID | None,
    lesson_id: uuid.UUID | None,
    provider: str,
    model: str,
    operation: str,
    cost_kind: str,
    quantity: Decimal,
    provider_event_id: str,
    occurred_at: datetime,
    unit: str = "tokens",
    raw: dict | None = None,
) -> AiUsageEvent:
    return AiUsageEvent(
        id=uuid.uuid4(),
        cohort_id=cohort_id,
        student_id=student_id,
        lesson_id=lesson_id,
        provider=provider,
        model=model,
        operation=operation,
        cost_kind=cost_kind,
        quantity=quantity,
        unit=unit,
        estimated_cost_usd=_usd(provider, model, cost_kind, quantity, unit=unit),
        provider_event_id=provider_event_id,
        raw=raw or {"seed": True, "operation": operation, "cost_kind": cost_kind},
        occurred_at=occurred_at,
    )


def _voice_turn_lines(
    *,
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_id: uuid.UUID,
    turn: int,
    base_time: datetime,
) -> list[AiUsageEvent]:
    """One Realtime turn (~12 min call split across turns) + transcription."""
    event_base = f"seed-voice-{student_id}-{lesson_id}-t{turn}"
    # ~90s student audio + ~120s agent audio per turn (600 + 1200 tokens/min logic)
    audio_in = Decimal(RNG.randint(800, 1400))
    audio_out = Decimal(RNG.randint(1600, 2800))
    cached_in = Decimal(RNG.randint(200, 600))
    text_in = Decimal(RNG.randint(400, 900))
    text_out = Decimal(RNG.randint(80, 200))
    transcribe_in = Decimal(RNG.randint(150, 350))
    transcribe_out = Decimal(RNG.randint(20, 60))

    when = base_time + timedelta(minutes=turn * 3)
    scope = dict(cohort_id=cohort_id, student_id=student_id, lesson_id=lesson_id)

    rows = [
        _line(
            **scope,
            provider="openai",
            model=REALTIME_MODEL,
            operation="realtime_response",
            cost_kind="realtime_audio_in",
            quantity=audio_in,
            provider_event_id=f"{event_base}:realtime:audio_in",
            occurred_at=when,
        ),
        _line(
            **scope,
            provider="openai",
            model=REALTIME_MODEL,
            operation="realtime_response",
            cost_kind="realtime_audio_out",
            quantity=audio_out,
            provider_event_id=f"{event_base}:realtime:audio_out",
            occurred_at=when,
        ),
        _line(
            **scope,
            provider="openai",
            model=REALTIME_MODEL,
            operation="realtime_response",
            cost_kind="realtime_audio_in_cached",
            quantity=cached_in,
            provider_event_id=f"{event_base}:realtime:audio_cached",
            occurred_at=when,
        ),
        _line(
            **scope,
            provider="openai",
            model=REALTIME_MODEL,
            operation="realtime_response",
            cost_kind="realtime_text_in",
            quantity=text_in,
            provider_event_id=f"{event_base}:realtime:text_in",
            occurred_at=when,
        ),
        _line(
            **scope,
            provider="openai",
            model=REALTIME_MODEL,
            operation="realtime_response",
            cost_kind="realtime_text_out",
            quantity=text_out,
            provider_event_id=f"{event_base}:realtime:text_out",
            occurred_at=when,
        ),
        _line(
            **scope,
            provider="openai",
            model=TRANSCRIBE_MODEL,
            operation="input_transcription",
            cost_kind="transcribe_audio_in",
            quantity=transcribe_in,
            provider_event_id=f"{event_base}:transcribe:audio_in",
            occurred_at=when,
        ),
        _line(
            **scope,
            provider="openai",
            model=TRANSCRIBE_MODEL,
            operation="input_transcription",
            cost_kind="transcribe_text_out",
            quantity=transcribe_out,
            provider_event_id=f"{event_base}:transcribe:text_out",
            occurred_at=when,
        ),
    ]
    return rows


def _chat_lines(
    *,
    cohort_id: uuid.UUID | None,
    student_id: uuid.UUID | None,
    lesson_id: uuid.UUID | None,
    operation: str,
    model: str,
    event_id: str,
    occurred_at: datetime,
    prompt: int,
    completion: int,
    cached: int = 0,
) -> list[AiUsageEvent]:
    scope = dict(cohort_id=cohort_id, student_id=student_id, lesson_id=lesson_id)
    rows: list[AiUsageEvent] = []
    fresh_in = Decimal(max(0, prompt - cached))
    if fresh_in > 0:
        rows.append(
            _line(
                **scope,
                provider="openai",
                model=model,
                operation=operation,
                cost_kind="chat_text_in",
                quantity=fresh_in,
                provider_event_id=f"{event_id}:chat:in",
                occurred_at=occurred_at,
            )
        )
    if cached > 0:
        rows.append(
            _line(
                **scope,
                provider="openai",
                model=model,
                operation=operation,
                cost_kind="chat_text_cached_in",
                quantity=Decimal(cached),
                provider_event_id=f"{event_id}:chat:cached",
                occurred_at=occurred_at,
            )
        )
    rows.append(
        _line(
            **scope,
            provider="openai",
            model=model,
            operation=operation,
            cost_kind="chat_text_out",
            quantity=Decimal(completion),
            provider_event_id=f"{event_id}:chat:out",
            occurred_at=occurred_at,
        )
    )
    return rows


async def seed_ai_usage_events(db: AsyncSession) -> int:
    """Insert demo usage if the table is empty. Returns rows written."""
    if await db.scalar(select(AiUsageEvent.id).limit(1)):
        return 0

    cohort = await db.scalar(
        select(Cohort).order_by(Cohort.created_at).limit(1)
    )
    if cohort is None:
        return 0

    track = await db.get(Track, cohort.track_id)
    lessons = list(
        (
            await db.scalars(
                select(Lesson)
                .join(Module, Lesson.module_id == Module.id)
                .where(Module.track_id == cohort.track_id)
                .order_by(Module.position, Lesson.position)
            )
        ).all()
    )
    if not lessons:
        return 0

    students = list(
        (
            await db.scalars(
                select(User).where(User.email.in_(("aluno@certai.app", "eriko@certai.app")))
            )
        ).all()
    )
    if len(students) < 2:
        return 0

    mariana = next(s for s in students if s.email == "aluno@certai.app")
    eriko = next(s for s in students if s.email == "eriko@certai.app")

    now = datetime.now(timezone.utc)
    base = now - timedelta(days=10)

    rows: list[AiUsageEvent] = []

    # --- Voz (maior peso): 4 turns Mariana aula 1, 3 turns Ériko aula 1, 2 Ériko aula 2
    for turn in range(4):
        rows.extend(
            _voice_turn_lines(
                cohort_id=cohort.id,
                student_id=mariana.id,
                lesson_id=lessons[0].id,
                turn=turn,
                base_time=base,
            )
        )
    for turn in range(3):
        rows.extend(
            _voice_turn_lines(
                cohort_id=cohort.id,
                student_id=eriko.id,
                lesson_id=lessons[0].id,
                turn=turn,
                base_time=base + timedelta(days=1),
            )
        )
    for turn in range(2):
        rows.extend(
            _voice_turn_lines(
                cohort_id=cohort.id,
                student_id=eriko.id,
                lesson_id=lessons[1].id,
                turn=turn,
                base_time=base + timedelta(days=3),
            )
        )

    # --- Motor + humanizador (WhatsApp / in-app)
    rows.extend(
        _chat_lines(
            cohort_id=cohort.id,
            student_id=mariana.id,
            lesson_id=lessons[0].id,
            operation="engine",
            model=ENGINE_MODEL,
            event_id=f"seed-engine-{mariana.id}-l0",
            occurred_at=base + timedelta(days=2, hours=4),
            prompt=4200,
            completion=380,
            cached=1800,
        )
    )
    rows.extend(
        _chat_lines(
            cohort_id=cohort.id,
            student_id=mariana.id,
            lesson_id=lessons[0].id,
            operation="humanizer",
            model=HUMANIZER_MODEL,
            event_id=f"seed-humanizer-{mariana.id}-l0",
            occurred_at=base + timedelta(days=2, hours=4, minutes=1),
            prompt=520,
            completion=410,
        )
    )
    rows.extend(
        _chat_lines(
            cohort_id=cohort.id,
            student_id=eriko.id,
            lesson_id=lessons[0].id,
            operation="engine",
            model=ENGINE_MODEL,
            event_id=f"seed-engine-{eriko.id}-l0",
            occurred_at=base + timedelta(days=2, hours=6),
            prompt=3100,
            completion=290,
            cached=900,
        )
    )

    # --- Avaliador (aula + módulo)
    rows.extend(
        _chat_lines(
            cohort_id=cohort.id,
            student_id=mariana.id,
            lesson_id=lessons[0].id,
            operation="evaluator",
            model=ENGINE_MODEL,
            event_id=f"seed-eval-lesson-{mariana.id}-l0",
            occurred_at=base + timedelta(days=4),
            prompt=8500,
            completion=650,
        )
    )
    rows.extend(
        _chat_lines(
            cohort_id=cohort.id,
            student_id=eriko.id,
            lesson_id=lessons[0].id,
            operation="evaluator",
            model=ENGINE_MODEL,
            event_id=f"seed-eval-lesson-{eriko.id}-l0",
            occurred_at=base + timedelta(days=4, hours=2),
            prompt=7200,
            completion=580,
        )
    )

    # --- Ingestão do relato (turma + aula, sem aluno)
    rows.extend(
        _chat_lines(
            cohort_id=cohort.id,
            student_id=None,
            lesson_id=lessons[0].id,
            operation="ingestion",
            model=ENGINE_MODEL,
            event_id=f"seed-ingest-note-{cohort.id}-l0",
            occurred_at=base + timedelta(days=1, hours=2),
            prompt=6000,
            completion=900,
        )
    )

    # --- Ingestão de material da trilha (sem turma — overhead)
    if track is not None:
        rows.extend(
            _chat_lines(
                cohort_id=None,
                student_id=None,
                lesson_id=None,
                operation="ingestion",
                model=ENGINE_MODEL,
                event_id=f"seed-ingest-track-{track.id}",
                occurred_at=base - timedelta(days=30),
                prompt=12000,
                completion=1800,
            )
        )

    # --- Resumo de histórico descartado (voz)
    rows.extend(
        _chat_lines(
            cohort_id=cohort.id,
            student_id=eriko.id,
            lesson_id=lessons[0].id,
            operation="summarizer",
            model=ENGINE_MODEL,
            event_id=f"seed-summarize-{eriko.id}-l0",
            occurred_at=base + timedelta(days=1, hours=5),
            prompt=4500,
            completion=420,
        )
    )

    # --- Transcrição Groq (relato do professor)
    rows.append(
        _line(
            cohort_id=cohort.id,
            student_id=None,
            lesson_id=lessons[1].id,
            provider="groq",
            model=GROQ_WHISPER,
            operation="transcription",
            cost_kind="transcribe_audio_seconds",
            quantity=Decimal("185"),
            unit="seconds",
            provider_event_id=f"seed-groq-{cohort.id}-l1",
            occurred_at=base + timedelta(days=3, hours=1),
        )
    )

    db.add_all(rows)
    await db.flush()
    return len(rows)
