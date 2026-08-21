"""Read-side aggregation over ai_usage_events (no AI, no per-row Python loops).

Every total comes from a SQL GROUP BY. The axis mirrors the layered assessments:
cohort -> student -> lesson.

Two rules run through all of it:
  * A row with `estimated_cost_usd IS NULL` has no known rate. It is counted in
    `unpriced_events` and never summed as zero -- a total that silently omits an
    unpriced model reads as complete when it is not.
  * Voice minutes are derived from audio tokens (~10 tokens/second), so every
    field carrying them is named `_est`. It is an approximation, not a clock.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Select, distinct, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cohort import Cohort, Enrollment
from app.models.track import Lesson, Module, Track
from app.models.usage import AiUsageEvent
from app.models.user import User

# --- Vocabulary -------------------------------------------------------------

COST_KIND_LABELS: dict[str, str] = {
    "realtime_audio_in": "Áudio de entrada (voz)",
    "realtime_audio_out": "Áudio de saída (voz)",
    "realtime_audio_in_cached": "Áudio em cache (voz)",
    "realtime_text_in": "Texto de entrada (voz)",
    "realtime_text_out": "Texto de saída (voz)",
    "realtime_text_in_cached": "Texto em cache (voz)",
    "realtime_image_in": "Imagem de entrada (voz)",
    "realtime_image_in_cached": "Imagem em cache (voz)",
    "transcribe_audio_in": "Áudio (transcrição)",
    "transcribe_text_in": "Texto de entrada (transcrição)",
    "transcribe_text_out": "Texto de saída (transcrição)",
    "transcribe_audio_seconds": "Duração de áudio (transcrição)",
    "chat_text_in": "Texto de entrada (chat)",
    "chat_text_cached_in": "Texto em cache (chat)",
    "chat_text_out": "Texto de saída (chat)",
}

OPERATION_LABELS: dict[str, str] = {
    "realtime_response": "Conversa por voz",
    "input_transcription": "Transcrição da fala do aluno",
    "engine": "Motor da Lira",
    "humanizer": "Humanizador",
    "evaluator": "Avaliador",
    "ingestion": "Ingestão de material",
    "summarizer": "Resumo de histórico",
    "transcription": "Transcrição do professor",
}

# Audio tokens billed by the Realtime API, used to derive call minutes.
_VOICE_AUDIO_KINDS = (
    "realtime_audio_in",
    "realtime_audio_out",
    "realtime_audio_in_cached",
)
# Everything the voice channel bills, for the voice-vs-rest split per lesson.
_VOICE_OPERATIONS = ("realtime_response", "input_transcription")

_AUDIO_TOKENS_PER_SECOND = Decimal("10")
_ZERO = Decimal("0")


def label_for_kind(kind: str) -> str:
    return COST_KIND_LABELS.get(kind, kind)


def label_for_operation(operation: str) -> str:
    return OPERATION_LABELS.get(operation, operation)


def default_window(
    date_from: datetime | None, date_to: datetime | None
) -> tuple[datetime, datetime]:
    """Last 30 days unless told otherwise. Period is a DB filter, not a UI one."""
    end = date_to or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = date_from or (end - timedelta(days=30))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start, end


# --- Rows -------------------------------------------------------------------


@dataclass(frozen=True)
class KindBreakdownRow:
    cost_kind: str
    label: str
    provider: str
    total_tokens: Decimal
    cost_usd: Decimal
    unpriced_events: int


@dataclass(frozen=True)
class LessonCostRow:
    lesson_id: uuid.UUID | None
    lesson_title: str
    module_title: str
    voice_minutes_est: float
    voice_cost_usd: Decimal
    other_cost_usd: Decimal
    cost_usd: Decimal
    unpriced_events: int


@dataclass(frozen=True)
class StudentCostRow:
    student_id: uuid.UUID | None
    student_name: str
    lesson_count: int
    voice_minutes_est: float
    cost_usd: Decimal
    cost_per_lesson_usd: Decimal
    unpriced_events: int


@dataclass(frozen=True)
class CohortCostRow:
    cohort_id: uuid.UUID
    cohort_title: str
    track_id: uuid.UUID | None
    track_title: str
    student_count: int
    lesson_count: int
    # Distinct (student, lesson) pairs with measured spend. The denominator that
    # answers "what does one assessment per student cost" -- total/lessons would
    # blend every student together and overstate it by the headcount.
    student_lesson_count: int
    voice_minutes_est: float
    cost_usd: Decimal
    cost_per_student_usd: Decimal
    cost_per_student_lesson_usd: Decimal
    unpriced_events: int


@dataclass(frozen=True)
class CohortsCostResult:
    cohorts: list[CohortCostRow]
    total_cost_usd: Decimal
    unattributed_cost_usd: Decimal
    unpriced_events: int
    models: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CohortCostDetailResult:
    cohort_id: uuid.UUID
    cohort_title: str
    track_title: str
    voice_minutes_est: float
    cost_usd: Decimal
    unpriced_events: int
    by_kind: list[KindBreakdownRow] = field(default_factory=list)
    students: list[StudentCostRow] = field(default_factory=list)
    models: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StudentCostDetailResult:
    cohort_id: uuid.UUID
    cohort_title: str
    student_id: uuid.UUID
    student_name: str
    voice_minutes_est: float
    cost_usd: Decimal
    unpriced_events: int
    by_kind: list[KindBreakdownRow] = field(default_factory=list)
    lessons: list[LessonCostRow] = field(default_factory=list)
    models: list[str] = field(default_factory=list)


# --- Shared SQL fragments ---------------------------------------------------


def _money(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.000001"))


def _tokens(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.001"))


def _minutes(audio_tokens: object) -> float:
    """Audio tokens -> minutes of call. ~10 tokens/second, per OpenAI."""
    tokens = Decimal(str(audio_tokens or 0))
    if tokens <= 0:
        return 0.0
    return float(
        (tokens / _AUDIO_TOKENS_PER_SECOND / Decimal("60")).quantize(Decimal("0.01"))
    )


def _cost_sum():
    return func.coalesce(func.sum(AiUsageEvent.estimated_cost_usd), 0)


def _unpriced_count():
    """Rows whose model has no rate. Surfaced, never folded into the total."""
    return func.count(AiUsageEvent.id).filter(
        AiUsageEvent.estimated_cost_usd.is_(None)
    )


def _voice_audio_tokens():
    return func.coalesce(
        func.sum(AiUsageEvent.quantity).filter(
            AiUsageEvent.cost_kind.in_(_VOICE_AUDIO_KINDS)
        ),
        0,
    )


def _voice_cost():
    return func.coalesce(
        func.sum(AiUsageEvent.estimated_cost_usd).filter(
            AiUsageEvent.operation.in_(_VOICE_OPERATIONS)
        ),
        0,
    )


def _apply_filters(
    stmt: Select,
    *,
    date_from: datetime,
    date_to: datetime,
    model: str | None = None,
) -> Select:
    stmt = stmt.where(
        AiUsageEvent.occurred_at >= date_from, AiUsageEvent.occurred_at <= date_to
    )
    if model:
        stmt = stmt.where(AiUsageEvent.model == model)
    return stmt


def _in_window(
    stmt: Select, *, date_from: datetime, date_to: datetime
) -> Select:
    """Compat: period-only. Prefer `_apply_filters` when model matters."""
    return _apply_filters(stmt, date_from=date_from, date_to=date_to)


def _safe_div(total: Decimal, count: int) -> Decimal:
    if count <= 0:
        return _ZERO
    return (total / Decimal(count)).quantize(Decimal("0.000001"))


async def _list_models(
    db: AsyncSession,
    *,
    date_from: datetime,
    date_to: datetime,
    extra_where: list | None = None,
) -> list[str]:
    """Distinct models in the period (ignores model filter so the select stays full)."""
    stmt = select(AiUsageEvent.model).distinct().order_by(AiUsageEvent.model)
    if extra_where:
        stmt = stmt.where(*extra_where)
    rows = (
        await db.execute(_apply_filters(stmt, date_from=date_from, date_to=date_to))
    ).all()
    return [str(row[0]) for row in rows if row[0]]


# --- Service ----------------------------------------------------------------


class UsageCostReadService:
    """Aggregated AI spend for the admin Costs area."""

    @staticmethod
    async def list_cohorts(
        db: AsyncSession,
        *,
        date_from: datetime,
        date_to: datetime,
        model: str | None = None,
    ) -> CohortsCostResult:
        stmt = (
            select(
                AiUsageEvent.cohort_id,
                Cohort.name.label("cohort_title"),
                Cohort.track_id,
                Track.title.label("track_title"),
                _cost_sum().label("cost"),
                _voice_audio_tokens().label("audio_tokens"),
                _unpriced_count().label("unpriced"),
                func.count(func.distinct(AiUsageEvent.student_id)).label("students"),
                func.count(func.distinct(AiUsageEvent.lesson_id)).label("lessons"),
                func.count(
                    distinct(tuple_(AiUsageEvent.student_id, AiUsageEvent.lesson_id))
                ).label("student_lessons"),
            )
            .join(Cohort, AiUsageEvent.cohort_id == Cohort.id)
            .join(Track, Cohort.track_id == Track.id)
            .group_by(AiUsageEvent.cohort_id, Cohort.name, Cohort.track_id, Track.title)
            .order_by(_cost_sum().desc())
        )
        rows = (
            await db.execute(
                _apply_filters(
                    stmt, date_from=date_from, date_to=date_to, model=model
                )
            )
        ).all()

        # Enrolled headcount, not "students who happened to spend": the cost per
        # student of a cohort where half the class never called is a real number.
        enrolled = dict(
            (
                await db.execute(
                    select(Enrollment.cohort_id, func.count(Enrollment.student_id))
                    .where(
                        Enrollment.cohort_id.in_([r.cohort_id for r in rows] or [None])
                    )
                    .group_by(Enrollment.cohort_id)
                )
            ).all()
        )

        cohorts: list[CohortCostRow] = []
        for row in rows:
            cost = _money(row.cost)
            students = int(enrolled.get(row.cohort_id) or row.students or 0)
            lessons = int(row.lessons or 0)
            student_lessons = int(row.student_lessons or 0)
            cohorts.append(
                CohortCostRow(
                    cohort_id=row.cohort_id,
                    cohort_title=row.cohort_title,
                    track_id=row.track_id,
                    track_title=row.track_title or "",
                    student_count=students,
                    lesson_count=lessons,
                    student_lesson_count=student_lessons,
                    voice_minutes_est=_minutes(row.audio_tokens),
                    cost_usd=cost,
                    cost_per_student_usd=_safe_div(cost, students),
                    cost_per_student_lesson_usd=_safe_div(cost, student_lessons),
                    unpriced_events=int(row.unpriced or 0),
                )
            )

        # Track-material ingestion has no cohort to charge. Reported apart so the
        # grand total stays honest without inflating any cohort's per-student cost.
        unattributed_stmt = select(_cost_sum()).where(AiUsageEvent.cohort_id.is_(None))
        unattributed = _money(
            (
                await db.execute(
                    _apply_filters(
                        unattributed_stmt,
                        date_from=date_from,
                        date_to=date_to,
                        model=model,
                    )
                )
            ).scalar_one()
        )
        unpriced_stmt = select(_unpriced_count())
        total_unpriced = int(
            (
                await db.execute(
                    _apply_filters(
                        unpriced_stmt,
                        date_from=date_from,
                        date_to=date_to,
                        model=model,
                    )
                )
            ).scalar_one()
            or 0
        )

        models = await _list_models(db, date_from=date_from, date_to=date_to)

        return CohortsCostResult(
            cohorts=cohorts,
            total_cost_usd=_money(
                sum((c.cost_usd for c in cohorts), _ZERO) + unattributed
            ),
            unattributed_cost_usd=unattributed,
            unpriced_events=total_unpriced,
            models=models,
        )

    @staticmethod
    async def cohort_detail(
        db: AsyncSession,
        *,
        cohort_id: uuid.UUID,
        date_from: datetime,
        date_to: datetime,
        model: str | None = None,
    ) -> CohortCostDetailResult | None:
        cohort = await db.get(Cohort, cohort_id)
        if cohort is None:
            return None
        track_title = (
            await db.scalar(select(Track.title).where(Track.id == cohort.track_id))
        ) or ""

        by_kind = await _kind_breakdown(
            db,
            extra_where=[AiUsageEvent.cohort_id == cohort_id],
            date_from=date_from,
            date_to=date_to,
            model=model,
        )

        student_stmt = (
            select(
                AiUsageEvent.student_id,
                User.name.label("student_name"),
                _cost_sum().label("cost"),
                _voice_audio_tokens().label("audio_tokens"),
                _unpriced_count().label("unpriced"),
                func.count(func.distinct(AiUsageEvent.lesson_id)).label("lessons"),
            )
            .outerjoin(User, AiUsageEvent.student_id == User.id)
            .where(AiUsageEvent.cohort_id == cohort_id)
            .group_by(AiUsageEvent.student_id, User.name)
            .order_by(_cost_sum().desc())
        )
        student_rows = (
            await db.execute(
                _apply_filters(
                    student_stmt, date_from=date_from, date_to=date_to, model=model
                )
            )
        ).all()

        students: list[StudentCostRow] = []
        for row in student_rows:
            cost = _money(row.cost)
            lessons = int(row.lessons or 0)
            students.append(
                StudentCostRow(
                    student_id=row.student_id,
                    # Cohort-level work (lesson-note ingestion) has no student.
                    student_name=row.student_name or "Custos da turma",
                    lesson_count=lessons,
                    voice_minutes_est=_minutes(row.audio_tokens),
                    cost_usd=cost,
                    cost_per_lesson_usd=_safe_div(cost, lessons),
                    unpriced_events=int(row.unpriced or 0),
                )
            )

        models = await _list_models(
            db,
            date_from=date_from,
            date_to=date_to,
            extra_where=[AiUsageEvent.cohort_id == cohort_id],
        )

        return CohortCostDetailResult(
            cohort_id=cohort.id,
            cohort_title=cohort.name,
            track_title=track_title,
            voice_minutes_est=sum(s.voice_minutes_est for s in students),
            cost_usd=_money(sum((s.cost_usd for s in students), _ZERO)),
            unpriced_events=sum(s.unpriced_events for s in students),
            by_kind=by_kind,
            students=students,
            models=models,
        )

    @staticmethod
    async def student_detail(
        db: AsyncSession,
        *,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        date_from: datetime,
        date_to: datetime,
        model: str | None = None,
    ) -> StudentCostDetailResult | None:
        cohort = await db.get(Cohort, cohort_id)
        student = await db.get(User, student_id)
        if cohort is None or student is None:
            return None

        scope_where = [
            AiUsageEvent.cohort_id == cohort_id,
            AiUsageEvent.student_id == student_id,
        ]
        by_kind = await _kind_breakdown(
            db,
            extra_where=scope_where,
            date_from=date_from,
            date_to=date_to,
            model=model,
        )

        lesson_stmt = (
            select(
                AiUsageEvent.lesson_id,
                Lesson.title.label("lesson_title"),
                Module.title.label("module_title"),
                _cost_sum().label("cost"),
                _voice_cost().label("voice_cost"),
                _voice_audio_tokens().label("audio_tokens"),
                _unpriced_count().label("unpriced"),
            )
            .outerjoin(Lesson, AiUsageEvent.lesson_id == Lesson.id)
            .outerjoin(Module, Lesson.module_id == Module.id)
            .where(*scope_where)
            .group_by(AiUsageEvent.lesson_id, Lesson.title, Module.title)
            .order_by(_cost_sum().desc())
        )
        rows = (
            await db.execute(
                _apply_filters(
                    lesson_stmt, date_from=date_from, date_to=date_to, model=model
                )
            )
        ).all()

        lessons: list[LessonCostRow] = []
        for row in rows:
            cost = _money(row.cost)
            voice = _money(row.voice_cost)
            lessons.append(
                LessonCostRow(
                    lesson_id=row.lesson_id,
                    lesson_title=row.lesson_title or "Sem aula atribuída",
                    module_title=row.module_title or "",
                    voice_minutes_est=_minutes(row.audio_tokens),
                    voice_cost_usd=voice,
                    other_cost_usd=_money(cost - voice),
                    cost_usd=cost,
                    unpriced_events=int(row.unpriced or 0),
                )
            )

        models = await _list_models(
            db, date_from=date_from, date_to=date_to, extra_where=scope_where
        )

        return StudentCostDetailResult(
            cohort_id=cohort.id,
            cohort_title=cohort.name,
            student_id=student.id,
            student_name=student.name,
            voice_minutes_est=sum(lesson.voice_minutes_est for lesson in lessons),
            cost_usd=_money(sum((lesson.cost_usd for lesson in lessons), _ZERO)),
            unpriced_events=sum(lesson.unpriced_events for lesson in lessons),
            by_kind=by_kind,
            lessons=lessons,
            models=models,
        )


async def _kind_breakdown(
    db: AsyncSession,
    *,
    extra_where: list,
    date_from: datetime,
    date_to: datetime,
    model: str | None = None,
) -> list[KindBreakdownRow]:
    """Where the money went, by billable kind. The 'why it cost that' table."""
    stmt = (
        select(
            AiUsageEvent.cost_kind,
            AiUsageEvent.provider,
            _cost_sum().label("cost"),
            func.coalesce(func.sum(AiUsageEvent.quantity), 0).label("tokens"),
            _unpriced_count().label("unpriced"),
        )
        .where(*extra_where)
        .group_by(AiUsageEvent.cost_kind, AiUsageEvent.provider)
        .order_by(_cost_sum().desc())
    )
    rows = (
        await db.execute(
            _apply_filters(stmt, date_from=date_from, date_to=date_to, model=model)
        )
    ).all()
    return [
        KindBreakdownRow(
            cost_kind=row.cost_kind,
            label=label_for_kind(row.cost_kind),
            provider=row.provider,
            total_tokens=_tokens(row.tokens),
            cost_usd=_money(row.cost),
            unpriced_events=int(row.unpriced or 0),
        )
        for row in rows
    ]
