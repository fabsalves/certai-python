"""Shared evaluator motor for layered student assessments.

What changes per layer is the input bundle; the LLM call, parse, and persist
path stay here.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.ai.client import get_openai
from app.core.config import settings
from app.models.assessment import AssessmentScope, Level, MicroScore, StudentAssessment
from app.services.ingestion import coerce_llm_text_field

logger = logging.getLogger(__name__)

EVALUATOR_SYSTEM_PROMPT = (
    "Você é um avaliador interno de compreensão. Não conversa com o aluno e não "
    "assume a persona de tutor. Recebe evidências do que o aluno demonstrou e "
    "julga livremente o quanto compreendeu no escopo indicado.\n\n"
    "PROIBIDO: nota numérica, percentual, média, checklist rígido ou heurística "
    "mecânica. O julgamento é qualitativo.\n\n"
    "Responda SOMENTE com um JSON contendo exatamente as chaves:\n"
    '- "level": "very_low" | "low" | "medium" | "high" | null '
    "(null quando não houver evidência suficiente para atribuir nível)\n"
    '- "assessment": parecer em português sobre o quanto o aluno compreendeu\n'
    '- "gaps": lacunas identificadas em português; string vazia se não houver'
)

_VALID_LEVELS = {level.value for level in Level}


def parse_level(raw: Any) -> Level | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        value = raw.strip().lower()
        if not value or value in ("null", "none"):
            return None
        if value in _VALID_LEVELS:
            return Level(value)
    return None


def format_micro_scores(scores: list[MicroScore], *, empty_label: str) -> str:
    if not scores:
        return empty_label
    lines: list[str] = []
    for score in scores:
        lines.append(
            f"- competência: {score.competency or '(sem nome)'}\n"
            f"  nível: {score.level.value}\n"
            f"  evidência: {score.evidence or '(sem evidência)'}"
        )
    return "\n".join(lines)


def format_child_assessments(
    rows: list[StudentAssessment],
    *,
    title_for: Callable[[StudentAssessment], str],
    empty_label: str,
) -> str:
    if not rows:
        return empty_label
    lines: list[str] = []
    for row in rows:
        level = row.level.value if row.level is not None else "null"
        lines.append(
            f"## {title_for(row)}\n"
            f"nível: {level}\n"
            f"parecer: {row.assessment or '(vazio)'}\n"
            f"lacunas: {row.gaps or '(vazio)'}"
        )
    return "\n\n".join(lines)


async def latest_assessments_for_scope_ids(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    scope: AssessmentScope,
    scope_fk_column: InstrumentedAttribute[uuid.UUID | None],
    scope_ids: list[uuid.UUID],
) -> list[StudentAssessment]:
    """Return the latest assessment per scope id (append-only → max created_at)."""
    if not scope_ids:
        return []

    rows = (
        await db.scalars(
            select(StudentAssessment)
            .where(
                StudentAssessment.cohort_id == cohort_id,
                StudentAssessment.student_id == student_id,
                StudentAssessment.scope == scope,
                scope_fk_column.in_(scope_ids),
            )
            .order_by(StudentAssessment.created_at.desc())
        )
    ).all()

    latest_by_id: dict[uuid.UUID, StudentAssessment] = {}
    for row in rows:
        key = getattr(row, scope_fk_column.key)
        if key is None or key in latest_by_id:
            continue
        latest_by_id[key] = row

    ordered: list[StudentAssessment] = []
    for scope_id in scope_ids:
        found = latest_by_id.get(scope_id)
        if found is not None:
            ordered.append(found)
    return ordered


async def load_micro_scores_for_lessons(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_ids: list[uuid.UUID],
) -> list[MicroScore]:
    if not lesson_ids:
        return []
    return list(
        (
            await db.scalars(
                select(MicroScore)
                .where(
                    MicroScore.cohort_id == cohort_id,
                    MicroScore.student_id == student_id,
                    MicroScore.lesson_id.in_(lesson_ids),
                )
                .order_by(MicroScore.created_at)
            )
        ).all()
    )


async def run_evaluator_and_persist(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    scope: AssessmentScope,
    user_prompt: str,
    lesson_id: uuid.UUID | None = None,
    module_id: uuid.UUID | None = None,
    track_id: uuid.UUID | None = None,
    log_context: str = "",
) -> StudentAssessment:
    """Call the evaluator model and append a StudentAssessment row."""
    client = get_openai()
    resp = await client.chat.completions.create(
        model=settings.EVALUATOR_MODEL,
        max_tokens=2048,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw_text = resp.choices[0].message.content or ""
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("assessment JSON parse failed %s", log_context or scope.value)
        payload = {"level": None, "assessment": raw_text, "gaps": ""}

    if not isinstance(payload, dict):
        payload = {"level": None, "assessment": str(payload), "gaps": ""}

    row = StudentAssessment(
        cohort_id=cohort_id,
        student_id=student_id,
        scope=scope,
        lesson_id=lesson_id,
        module_id=module_id,
        track_id=track_id,
        level=parse_level(payload.get("level")),
        assessment=coerce_llm_text_field(payload.get("assessment", "")),
        gaps=coerce_llm_text_field(payload.get("gaps", "")),
    )
    db.add(row)
    await db.flush()
    return row
