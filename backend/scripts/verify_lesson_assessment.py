"""Verify layered student assessments (lesson / module / track).

Modes:
  1) Trigger wiring (no DB / Celery / Lira):
       python scripts/verify_lesson_assessment.py --check-trigger

  2) Direct assessment (iterate without triggers):
       python scripts/verify_lesson_assessment.py \\
         --scope lesson --cohort-id UUID --student-id UUID --lesson-id UUID

       python scripts/verify_lesson_assessment.py \\
         --scope module --cohort-id UUID --student-id UUID --module-id UUID

       python scripts/verify_lesson_assessment.py \\
         --scope track --cohort-id UUID --student-id UUID --track-id UUID

     With --force, runs even if progress/preconditions look incomplete (warns only).
     Legacy: omitting --scope with --lesson-id implies --scope lesson.

Usage (from backend/ with venv active).
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import sys
import uuid

sys.path.insert(0, ".")


def test_trigger_wiring() -> None:
    """Assert conclude/advance → lesson task; lesson task → module; module → track."""
    from app.ai import tools
    from app.services.assessment import completion as completion_mod
    from app.services.assessment import lesson_assessment_service, read_service
    from app.services.student_progress_service import StudentProgressService
    from app.workers import tasks

    conclude_src = inspect.getsource(tools._conclude_lesson)
    assert "enqueue_after_commit" in conclude_src
    assert "assess_student_lesson" in conclude_src
    print("OK _conclude_lesson enfileira assess_student_lesson via enqueue_after_commit")

    advance_src = inspect.getsource(StudentProgressService.close_by_advance)
    assert "enqueue_after_commit" in advance_src
    assert "assess_student_lesson" in advance_src
    print("OK close_by_advance enfileira assess_student_lesson via enqueue_after_commit")

    other_src = inspect.getsource(StudentProgressService._close_other_active_lessons)
    assert "close_by_advance" in other_src
    print("OK _close_other_active_lessons reusa close_by_advance")

    gate_src = inspect.getsource(completion_mod.module_lessons_all_concluded)
    assert "ENCERRADA_POR_AVANCO" in gate_src
    assert "CONCLUIDA" in gate_src
    print("OK module_lessons_all_concluded aceita CONCLUIDA | ENCERRADA_POR_AVANCO")

    lesson_svc_src = inspect.getsource(lesson_assessment_service)
    assert "encerrada_por_avanco" in lesson_svc_src
    assert "Como esta aula foi encerrada" in lesson_svc_src
    print("OK prompt de aula inclui status de encerramento / evidência")

    read_src = inspect.getsource(read_service.StudentAssessmentReadService.latest_lesson_assessments)
    assert "ENCERRADA_POR_AVANCO" in read_src
    print("OK pending da aula inclui ENCERRADA_POR_AVANCO")

    lesson_src = inspect.getsource(tasks._assess_student_lesson)
    assert "module_lessons_all_concluded" in lesson_src
    assert "assess_student_module.delay" in lesson_src
    print("OK _assess_student_lesson encadeia assess_student_module quando módulo completo")

    module_src = inspect.getsource(tasks._assess_student_module)
    assert "track_modules_all_assessed" in module_src
    assert "assess_student_track.delay" in module_src
    print(
        "OK _assess_student_module encadeia assess_student_track "
        "quando todos os módulos têm avaliação"
    )

    # Module/track services must not pull conversations.
    from app.services.assessment import module_assessment_service, track_assessment_service

    module_src = inspect.getsource(module_assessment_service)
    track_src = inspect.getsource(track_assessment_service)
    assert "list_lesson_messages" not in module_src
    assert "list_lesson_messages" not in track_src
    assert "conversation_service" not in module_src
    assert "conversation_service" not in track_src
    print("OK módulo e trilha NÃO leem conversas (sem conversation_service)")

    assert "## Material do módulo" in module_src
    assert "module.description" in module_src
    assert "## Material do módulo" not in lesson_svc_src
    assert "## Material do módulo" not in track_src
    print("OK avaliação de módulo usa o catálogo do módulo; aula e trilha não")

    from app.services.assessment.module_assessment_service import _build_user_prompt

    filled = _build_user_prompt(
        module_title="Fundamentos",
        module_description="Separar fato de interpretação.",
        lesson_assessments_block="(nenhuma)",
        micro_scores_block="(nenhum)",
    )
    assert "## Material do módulo" in filled
    assert "Separar fato de interpretação." in filled
    empty = _build_user_prompt(
        module_title="Fundamentos",
        module_description="",
        lesson_assessments_block="(nenhuma)",
        micro_scores_block="(nenhum)",
    )
    assert "(sem conteúdo cadastrado)" in empty
    print("OK prompt de módulo inclui material cadastrado (ou marca vazio)")


async def test_settled_gating_mixed_statuses() -> None:
    """Module gate treats CONCLUIDA + ENCERRADA_POR_AVANCO as a full set."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.models.student_progress import StudentLessonProgressStatus
    from app.services.assessment.completion import module_lessons_all_concluded

    lesson_a = MagicMock(id=uuid.uuid4())
    lesson_b = MagicMock(id=uuid.uuid4())
    captured: dict = {}

    async def fake_scalars(stmt):
        captured["stmt"] = stmt
        return MagicMock(all=MagicMock(return_value=[lesson_a.id, lesson_b.id]))

    db = AsyncMock()
    db.scalars = fake_scalars

    with patch(
        "app.services.assessment.completion.active_lessons_for_module",
        new=AsyncMock(return_value=[lesson_a, lesson_b]),
    ):
        ok = await module_lessons_all_concluded(
            db,
            cohort_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            module_id=uuid.uuid4(),
        )
    assert ok is True

    sql = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert StudentLessonProgressStatus.CONCLUIDA.value in sql
    assert StudentLessonProgressStatus.ENCERRADA_POR_AVANCO.value in sql
    print("OK gating misto: query inclui CONCLUIDA e ENCERRADA_POR_AVANCO")


async def _print_persisted(row) -> None:
    level = row.level.value if row.level is not None else None
    print(f"  assessment_id: {row.id}")
    print(f"  scope: {row.scope.value}")
    print(f"  level: {level}")
    print(f"  assessment: {row.assessment[:500]}")
    print(f"  gaps: {row.gaps[:500]}")


async def run_direct_lesson(
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_id: uuid.UUID,
    *,
    force: bool = False,
) -> None:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.assessment import AssessmentScope, StudentAssessment
    from app.services.assessment.lesson_assessment_service import LessonAssessmentService
    from app.services.student_progress_service import StudentProgressService

    async with SessionLocal() as db:
        progress = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        if progress is None or progress.concluded_at is None:
            msg = (
                "Progresso não encontrado ou aula ainda não concluída "
                f"(cohort={cohort_id} student={student_id} lesson={lesson_id})."
            )
            if force:
                print(f"AVISO: {msg} Continuando com --force.")
            else:
                raise SystemExit(msg)

        row = await LessonAssessmentService.assess(
            db, cohort_id, student_id, lesson_id
        )
        await db.commit()

        persisted = await db.scalar(
            select(StudentAssessment)
            .where(
                StudentAssessment.cohort_id == cohort_id,
                StudentAssessment.student_id == student_id,
                StudentAssessment.scope == AssessmentScope.LESSON,
                StudentAssessment.lesson_id == lesson_id,
            )
            .order_by(StudentAssessment.created_at.desc())
            .limit(1)
        )
        assert persisted is not None, "StudentAssessment não foi persistido"
        assert persisted.id == row.id
        print("OK avaliação de aula persistida")
        await _print_persisted(persisted)


async def run_direct_module(
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    module_id: uuid.UUID,
    *,
    force: bool = False,
) -> None:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.assessment import AssessmentScope, StudentAssessment
    from app.services.assessment.completion import module_lessons_all_concluded
    from app.services.assessment.module_assessment_service import ModuleAssessmentService

    async with SessionLocal() as db:
        complete = await module_lessons_all_concluded(
            db,
            cohort_id=cohort_id,
            student_id=student_id,
            module_id=module_id,
        )
        if not complete:
            msg = (
                "Nem todas as aulas ativas do módulo estão terminais "
                "(CONCLUIDA ou ENCERRADA_POR_AVANCO) "
                f"(cohort={cohort_id} student={student_id} module={module_id})."
            )
            if force:
                print(f"AVISO: {msg} Continuando com --force.")
            else:
                raise SystemExit(msg)

        print(
            "INFO: avaliação de módulo NÃO lê conversas — "
            "insumos = avaliações de aula + micro-scores do módulo."
        )
        row = await ModuleAssessmentService.assess(
            db, cohort_id, student_id, module_id
        )
        await db.commit()

        persisted = await db.scalar(
            select(StudentAssessment)
            .where(
                StudentAssessment.cohort_id == cohort_id,
                StudentAssessment.student_id == student_id,
                StudentAssessment.scope == AssessmentScope.MODULE,
                StudentAssessment.module_id == module_id,
            )
            .order_by(StudentAssessment.created_at.desc())
            .limit(1)
        )
        assert persisted is not None, "StudentAssessment de módulo não foi persistido"
        assert persisted.id == row.id
        print("OK avaliação de módulo persistida")
        await _print_persisted(persisted)


async def run_direct_track(
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    track_id: uuid.UUID,
    *,
    force: bool = False,
) -> None:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.assessment import AssessmentScope, StudentAssessment
    from app.services.assessment.completion import track_modules_all_assessed
    from app.services.assessment.track_assessment_service import TrackAssessmentService

    async with SessionLocal() as db:
        complete = await track_modules_all_assessed(
            db,
            cohort_id=cohort_id,
            student_id=student_id,
            track_id=track_id,
        )
        if not complete:
            msg = (
                "Nem todos os módulos ativos da trilha têm avaliação de módulo "
                f"(cohort={cohort_id} student={student_id} track={track_id})."
            )
            if force:
                print(f"AVISO: {msg} Continuando com --force.")
            else:
                raise SystemExit(msg)

        print(
            "INFO: avaliação de trilha NÃO lê conversas — "
            "insumos = avaliações de módulo + micro-scores da trilha."
        )
        row = await TrackAssessmentService.assess(
            db, cohort_id, student_id, track_id
        )
        await db.commit()

        persisted = await db.scalar(
            select(StudentAssessment)
            .where(
                StudentAssessment.cohort_id == cohort_id,
                StudentAssessment.student_id == student_id,
                StudentAssessment.scope == AssessmentScope.TRACK,
                StudentAssessment.track_id == track_id,
            )
            .order_by(StudentAssessment.created_at.desc())
            .limit(1)
        )
        assert persisted is not None, "StudentAssessment de trilha não foi persistido"
        assert persisted.id == row.id
        print("OK avaliação de trilha persistida")
        await _print_persisted(persisted)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify layered assessment flow")
    parser.add_argument(
        "--check-trigger",
        action="store_true",
        help="Only assert trigger/chain wiring (no DB)",
    )
    parser.add_argument(
        "--scope",
        choices=("lesson", "module", "track"),
        default=None,
        help="Assessment scope for direct mode",
    )
    parser.add_argument("--cohort-id", type=uuid.UUID, default=None)
    parser.add_argument("--student-id", type=uuid.UUID, default=None)
    parser.add_argument("--lesson-id", type=uuid.UUID, default=None)
    parser.add_argument("--module-id", type=uuid.UUID, default=None)
    parser.add_argument("--track-id", type=uuid.UUID, default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if completion preconditions are not met",
    )
    args = parser.parse_args()

    if args.check_trigger:
        test_trigger_wiring()
        asyncio.run(test_settled_gating_mixed_statuses())
        print("\nChecagem do gatilho passou.")
        return

    scope = args.scope
    if scope is None and args.lesson_id is not None:
        scope = "lesson"
    if scope is None:
        parser.error("modo direto exige --scope (ou --lesson-id legado) ou --check-trigger")

    if args.cohort_id is None or args.student_id is None:
        parser.error("modo direto exige --cohort-id e --student-id")

    if scope == "lesson":
        if args.lesson_id is None:
            parser.error("--scope lesson exige --lesson-id")
        asyncio.run(
            run_direct_lesson(
                args.cohort_id,
                args.student_id,
                args.lesson_id,
                force=args.force,
            )
        )
    elif scope == "module":
        if args.module_id is None:
            parser.error("--scope module exige --module-id")
        asyncio.run(
            run_direct_module(
                args.cohort_id,
                args.student_id,
                args.module_id,
                force=args.force,
            )
        )
    else:
        if args.track_id is None:
            parser.error("--scope track exige --track-id")
        asyncio.run(
            run_direct_track(
                args.cohort_id,
                args.student_id,
                args.track_id,
                force=args.force,
            )
        )

    print("\nAvaliação direta concluída.")


if __name__ == "__main__":
    main()
