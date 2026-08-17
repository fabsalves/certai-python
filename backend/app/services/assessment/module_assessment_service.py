"""Module-scope student assessment.

Inputs are hierarchical (latest lesson assessments + micro-scores in the module).
Does NOT read conversations.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentScope, StudentAssessment
from app.models.track import Module
from app.services.assessment.completion import active_lessons_for_module
from app.services.assessment.evaluator import (
    format_child_assessments,
    format_micro_scores,
    latest_assessments_for_scope_ids,
    load_micro_scores_for_lessons,
    run_evaluator_and_persist,
)


def _build_user_prompt(
    *,
    module_title: str,
    module_description: str,
    lesson_assessments_block: str,
    micro_scores_block: str,
) -> str:
    return (
        f"# Escopo: módulo\n"
        f"# Módulo: {module_title}\n\n"
        f"## Material do módulo\n{module_description or '(sem conteúdo cadastrado)'}\n\n"
        "Julgue a compreensão do aluno neste módulo a partir do material do "
        "módulo, das avaliações de aula (mais recentes) e dos micro-scores do "
        "módulo. Não há conversas neste escopo.\n\n"
        f"## Avaliações de aula do módulo\n{lesson_assessments_block}\n\n"
        f"## Micro-scores do aluno no módulo\n{micro_scores_block}"
    )


class ModuleAssessmentService:
    @staticmethod
    async def assess(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        module_id: uuid.UUID,
    ) -> StudentAssessment:
        """Build module inputs (no conversations), call evaluator, persist."""
        module = await db.get(Module, module_id)
        if module is None:
            raise ValueError(f"Module not found: {module_id}")

        lessons = await active_lessons_for_module(db, module_id)
        lesson_ids = [lesson.id for lesson in lessons]
        title_by_lesson_id = {lesson.id: lesson.title for lesson in lessons}

        lesson_assessments = await latest_assessments_for_scope_ids(
            db,
            cohort_id=cohort_id,
            student_id=student_id,
            scope=AssessmentScope.LESSON,
            scope_fk_column=StudentAssessment.lesson_id,
            scope_ids=lesson_ids,
        )

        scores = await load_micro_scores_for_lessons(
            db,
            cohort_id=cohort_id,
            student_id=student_id,
            lesson_ids=lesson_ids,
        )

        user_prompt = _build_user_prompt(
            module_title=module.title,
            module_description=module.description,
            lesson_assessments_block=format_child_assessments(
                lesson_assessments,
                title_for=lambda row: (
                    f"Aula: {title_by_lesson_id.get(row.lesson_id, row.lesson_id)}"
                ),
                empty_label="(nenhuma avaliação de aula neste módulo)",
            ),
            micro_scores_block=format_micro_scores(
                scores,
                empty_label="(nenhum micro-score registrado neste módulo)",
            ),
        )

        return await run_evaluator_and_persist(
            db,
            cohort_id=cohort_id,
            student_id=student_id,
            scope=AssessmentScope.MODULE,
            user_prompt=user_prompt,
            lesson_id=None,
            module_id=module_id,
            track_id=None,
            log_context=(
                f"cohort={cohort_id} student={student_id} module={module_id}"
            ),
        )
