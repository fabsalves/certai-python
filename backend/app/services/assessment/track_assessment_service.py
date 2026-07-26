"""Track-scope student assessment.

Inputs are hierarchical (latest module assessments + micro-scores in the track).
Does NOT read conversations.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentScope, StudentAssessment
from app.models.track import Track
from app.services.assessment.completion import (
    active_lesson_ids_for_track,
    active_modules_for_track,
)
from app.services.assessment.evaluator import (
    format_child_assessments,
    format_micro_scores,
    latest_assessments_for_scope_ids,
    load_micro_scores_for_lessons,
    run_evaluator_and_persist,
)


def _build_user_prompt(
    *,
    track_title: str,
    module_assessments_block: str,
    micro_scores_block: str,
) -> str:
    return (
        f"# Escopo: trilha\n"
        f"# Trilha: {track_title}\n\n"
        "Julgue a compreensão do aluno nesta trilha a partir das avaliações de "
        "módulo (mais recentes) e dos micro-scores da trilha. Não há conversas "
        "neste escopo.\n\n"
        f"## Avaliações de módulo da trilha\n{module_assessments_block}\n\n"
        f"## Micro-scores do aluno na trilha\n{micro_scores_block}"
    )


class TrackAssessmentService:
    @staticmethod
    async def assess(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        track_id: uuid.UUID,
    ) -> StudentAssessment:
        """Build track inputs (no conversations), call evaluator, persist."""
        track = await db.get(Track, track_id)
        if track is None:
            raise ValueError(f"Track not found: {track_id}")

        modules = await active_modules_for_track(db, track_id)
        module_ids = [module.id for module in modules]
        title_by_module_id = {module.id: module.title for module in modules}

        module_assessments = await latest_assessments_for_scope_ids(
            db,
            cohort_id=cohort_id,
            student_id=student_id,
            scope=AssessmentScope.MODULE,
            scope_fk_column=StudentAssessment.module_id,
            scope_ids=module_ids,
        )

        lesson_ids = await active_lesson_ids_for_track(db, track_id)
        scores = await load_micro_scores_for_lessons(
            db,
            cohort_id=cohort_id,
            student_id=student_id,
            lesson_ids=lesson_ids,
        )

        user_prompt = _build_user_prompt(
            track_title=track.title,
            module_assessments_block=format_child_assessments(
                module_assessments,
                title_for=lambda row: (
                    f"Módulo: {title_by_module_id.get(row.module_id, row.module_id)}"
                ),
                empty_label="(nenhuma avaliação de módulo nesta trilha)",
            ),
            micro_scores_block=format_micro_scores(
                scores,
                empty_label="(nenhum micro-score registrado nesta trilha)",
            ),
        )

        return await run_evaluator_and_persist(
            db,
            cohort_id=cohort_id,
            student_id=student_id,
            scope=AssessmentScope.TRACK,
            user_prompt=user_prompt,
            lesson_id=None,
            module_id=None,
            track_id=track_id,
            log_context=(
                f"cohort={cohort_id} student={student_id} track={track_id}"
            ),
        )
