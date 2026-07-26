"""Lesson-scope student assessment — external evaluator role (not Lira)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_openai
from app.core.config import settings
from app.models.assessment import (
    AssessmentScope,
    CohortLessonNote,
    Level,
    MicroScore,
    StudentAssessment,
)
from app.models.track import Lesson
from app.services.conversation_service import list_lesson_messages
from app.services.ingestion import coerce_llm_text_field

logger = logging.getLogger(__name__)

EVALUATOR_SYSTEM_PROMPT = (
    "Você é um avaliador interno de compreensão. Não conversa com o aluno e não "
    "assume a persona de tutor. Recebe o que a aula EXIGIA (material + relato do "
    "professor na turma) e o que o aluno DEMONSTROU (micro-scores com evidência + "
    "conversa). Julgue livremente o quanto o aluno compreendeu aquela aula.\n\n"
    "PROIBIDO: nota numérica, percentual, média, checklist rígido ou heurística "
    "mecânica. O julgamento é qualitativo.\n\n"
    "Responda SOMENTE com um JSON contendo exatamente as chaves:\n"
    '- "level": "very_low" | "low" | "medium" | "high" | null '
    "(null quando não houver evidência suficiente para atribuir nível)\n"
    '- "assessment": parecer em português sobre o quanto o aluno compreendeu\n'
    '- "gaps": lacunas identificadas em português; string vazia se não houver'
)

_VALID_LEVELS = {level.value for level in Level}


def _parse_level(raw: Any) -> Level | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        value = raw.strip().lower()
        if not value or value in ("null", "none"):
            return None
        if value in _VALID_LEVELS:
            return Level(value)
    return None


def _format_micro_scores(scores: list[MicroScore]) -> str:
    if not scores:
        return "(nenhum micro-score registrado nesta aula)"
    lines: list[str] = []
    for score in scores:
        lines.append(
            f"- competência: {score.competency or '(sem nome)'}\n"
            f"  nível: {score.level.value}\n"
            f"  evidência: {score.evidence or '(sem evidência)'}"
        )
    return "\n".join(lines)


def _format_conversation(messages: list) -> str:
    if not messages:
        return "(nenhuma mensagem nesta aula)"
    lines: list[str] = []
    for msg in messages:
        author = msg.author.value if hasattr(msg.author, "value") else str(msg.author)
        lines.append(f"[{author}] {msg.content}")
    return "\n".join(lines)


def _format_cohort_note(note: CohortLessonNote | None) -> str:
    if note is None:
        return "(sem relato do professor para esta turma/aula)"
    return (
        f"## Resumo\n{note.summary or '(vazio)'}\n\n"
        f"## Pontos pouco claros\n{note.unclear_points or '(vazio)'}\n\n"
        f"## Base de conhecimento do anexo\n{note.attachment_knowledge_base or '(vazio)'}\n\n"
        f"## Transcrição / relato do professor\n{note.professor_transcript or '(vazio)'}"
    )


def _build_user_prompt(
    *,
    lesson_title: str,
    lesson_content: str,
    note_block: str,
    micro_scores_block: str,
    conversation_block: str,
) -> str:
    return (
        f"# Aula: {lesson_title}\n\n"
        f"## Material da aula\n{lesson_content or '(sem conteúdo cadastrado)'}\n\n"
        f"## Escopo da turma (relato do professor)\n{note_block}\n\n"
        f"## Micro-scores do aluno nesta aula\n{micro_scores_block}\n\n"
        f"## Conversa do aluno nesta aula\n{conversation_block}"
    )


class LessonAssessmentService:
    @staticmethod
    async def assess(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> StudentAssessment:
        """Build inputs, call the evaluator model, persist an append-only row."""
        lesson = await db.get(Lesson, lesson_id)
        if lesson is None:
            raise ValueError(f"Lesson not found: {lesson_id}")

        note = await db.scalar(
            select(CohortLessonNote)
            .where(
                CohortLessonNote.cohort_id == cohort_id,
                CohortLessonNote.lesson_id == lesson_id,
            )
            .order_by(CohortLessonNote.created_at.desc())
            .limit(1)
        )

        scores = (
            await db.scalars(
                select(MicroScore)
                .where(
                    MicroScore.cohort_id == cohort_id,
                    MicroScore.student_id == student_id,
                    MicroScore.lesson_id == lesson_id,
                )
                .order_by(MicroScore.created_at)
            )
        ).all()

        messages = await list_lesson_messages(db, cohort_id, student_id, lesson_id)

        user_prompt = _build_user_prompt(
            lesson_title=lesson.title,
            lesson_content=lesson.content,
            note_block=_format_cohort_note(note),
            micro_scores_block=_format_micro_scores(list(scores)),
            conversation_block=_format_conversation(list(messages)),
        )

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
            logger.warning(
                "lesson assessment JSON parse failed cohort=%s student=%s lesson=%s",
                cohort_id,
                student_id,
                lesson_id,
            )
            payload = {"level": None, "assessment": raw_text, "gaps": ""}

        if not isinstance(payload, dict):
            payload = {"level": None, "assessment": str(payload), "gaps": ""}

        level = _parse_level(payload.get("level"))
        assessment_text = coerce_llm_text_field(payload.get("assessment", ""))
        gaps_text = coerce_llm_text_field(payload.get("gaps", ""))

        row = StudentAssessment(
            cohort_id=cohort_id,
            student_id=student_id,
            scope=AssessmentScope.LESSON,
            lesson_id=lesson_id,
            module_id=None,
            track_id=None,
            level=level,
            assessment=assessment_text,
            gaps=gaps_text,
        )
        db.add(row)
        await db.flush()
        return row
