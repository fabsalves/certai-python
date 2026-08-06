"""Verify mid-track join: claim orphan + catch-up (requires seeded DB).

Usage (from backend/ with venv active):
  python scripts/verify_mid_join.py
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import uuid
from unittest.mock import patch

sys.path.insert(0, ".")

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.cohort import (
    Cohort,
    CohortModuleProfessor,
    CohortModuleStudent,
    CohortProgress,
    Enrollment,
)
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.models.user import User
from app.services.assessment.completion import module_lessons_all_concluded
from app.services.cohort import ModuleClassService
from app.services.cohort.mid_join_service import MidJoinService
from app.services.track_structure import ordered_active_lessons


def test_wiring() -> None:
    from app.api.v1 import cohorts as cohorts_api
    from app.services.cohort import mid_join_service

    assert "catch_up_on_enroll" in inspect.getsource(cohorts_api.enroll)
    assert "catch_up_on_enroll" in inspect.getsource(cohorts_api.enroll_bulk)
    assert "catch_up_roster_additions" in inspect.getsource(
        cohorts_api._replace_module_professors
    )
    assert hasattr(cohorts_api, "claim_class_student")
    assert hasattr(cohorts_api, "list_unassigned_students")
    assert "Vincule-os à sua turma" in inspect.getsource(cohorts_api)
    src = inspect.getsource(mid_join_service.MidJoinService.catch_up_student_to_class)
    assert "ENCERRADA_POR_AVANCO" in inspect.getsource(mid_join_service)
    assert "_ensure_disparada" in src
    print("OK wiring: enroll/roster/claim/catch-up/mensagem 400")


async def _load_turma1():
    async with SessionLocal() as db:
        cohort = await db.scalar(select(Cohort).where(Cohort.name == "VPF, Turma 1"))
        if cohort is None:
            raise RuntimeError("VPF, Turma 1 ausente — rode bin/db-reset")
        ana = await db.scalar(select(User).where(User.email == "prof@certai.app"))
        pedro = await db.scalar(
            select(User).where(User.email == "pedro.almeida@certai.app")
        )
        if ana is None or pedro is None:
            raise RuntimeError("Usuários seed ausentes")
        lessons = await ordered_active_lessons(db, cohort.track_id)
        fund_module_id = lessons[0].module_id
        ana_class = await ModuleClassService.class_of_professor(
            db, cohort.id, fund_module_id, ana.id
        )
        if ana_class is None:
            raise RuntimeError("Ana sem classe em Fundamentos")
        return cohort.id, fund_module_id, ana.id, pedro.id, ana_class.id, [
            l.id for l in lessons if l.module_id == fund_module_id
        ]


async def run_flow() -> None:
    cohort_id, module_id, ana_id, pedro_id, ana_class_id, fund_lesson_ids = (
        await _load_turma1()
    )

    async with SessionLocal() as db:
        cohort = await db.get(Cohort, cohort_id)
        ana_class = await db.get(CohortModuleProfessor, ana_class_id)
        pedro = await db.get(User, pedro_id)

        # Ensure Pedro enrolled and unassigned in Fundamentos.
        enrolled = await db.scalar(
            select(Enrollment.id).where(
                Enrollment.cohort_id == cohort_id, Enrollment.student_id == pedro_id
            )
        )
        if enrolled is None:
            db.add(Enrollment(cohort_id=cohort_id, student_id=pedro_id))
            await db.flush()
            print("OK matriculou Pedro")
        else:
            print("OK Pedro já matriculado")

        # Clear any prior Fundamentos roster for Pedro.
        classes = await ModuleClassService.classes_of_module(db, cohort_id, module_id)
        await db.execute(
            delete(CohortModuleStudent).where(
                CohortModuleStudent.student_id == pedro_id,
                CohortModuleStudent.module_professor_id.in_([c.id for c in classes]),
            )
        )
        # Clear Pedro progress on Fundamentos so catch-up is measurable.
        for lesson_id in fund_lesson_ids:
            row = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.student_id == pedro_id,
                    StudentLessonProgress.lesson_id == lesson_id,
                )
            )
            if row is not None:
                await db.delete(row)
        await db.flush()

        unassigned = await ModuleClassService.unassigned_student_ids(
            db, cohort_id, module_id
        )
        assert pedro_id in unassigned, "Pedro deveria estar sem grupo"
        print("OK Pedro está unassigned — complete seria bloqueado")

        closed_before = set(
            (
                await db.scalars(
                    select(CohortProgress.lesson_id).where(
                        CohortProgress.cohort_id == cohort_id,
                        CohortProgress.module_professor_id == ana_class_id,
                    )
                )
            ).all()
        )
        print(f"INFO aulas já fechadas pela Ana: {len(closed_before)}")

        enqueues: list[tuple] = []

        def capture(db_sess, task, *args, **kwargs):
            enqueues.append((getattr(task, "name", str(task)), args))

        with patch("app.core.db_events.enqueue_after_commit", side_effect=capture):
            module_class = await MidJoinService.claim_student(
                db, cohort, module_id, ana_id, pedro_id
            )
        await db.commit()

        assert module_class.id == ana_class_id
        unassigned_after = await ModuleClassService.unassigned_student_ids(
            db, cohort_id, module_id
        )
        assert pedro_id not in unassigned_after
        print("OK claim: Pedro saiu do unassigned")

        # Terminal rows for every lesson Ana already closed.
        for lesson_id in closed_before:
            prog = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.student_id == pedro_id,
                    StudentLessonProgress.lesson_id == lesson_id,
                )
            )
            assert prog is not None, f"faltou progress em {lesson_id}"
            assert (
                prog.status == StudentLessonProgressStatus.ENCERRADA_POR_AVANCO
            ), prog.status
        print(
            f"OK catch-up: {len(closed_before)} aula(s) → ENCERRADA_POR_AVANCO "
            f"({len(enqueues)} enqueue(s))"
        )
        assert len(enqueues) == len(closed_before)

        next_id = await MidJoinService.next_open_lesson_id(db, cohort, ana_class)
        if next_id is not None:
            prog = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.student_id == pedro_id,
                    StudentLessonProgress.lesson_id == next_id,
                )
            )
            assert prog is not None
            assert prog.status == StudentLessonProgressStatus.DISPARADA
            print("OK próxima aula da classe → DISPARADA")
        else:
            print("INFO módulo da Ana já fechado — sem DISPARADA (esperado)")

        # If Ana closed all Fundamentos lessons, module gate should pass for Pedro
        # after catch-up (all terminal).
        settled = await module_lessons_all_concluded(
            db,
            cohort_id=cohort_id,
            student_id=pedro_id,
            module_id=module_id,
        )
        if len(closed_before) == len(fund_lesson_ids):
            assert settled is True
            print("OK module_lessons_all_concluded=True após catch-up completo")
        else:
            print(f"INFO module settled={settled} (Ana ainda tem aula aberta)")

        print(f"\nPedro ({pedro.name}) vinculado à turma da Ana com catch-up.")


async def main() -> None:
    test_wiring()
    await run_flow()
    print("\nverify_mid_join passou.")


if __name__ == "__main__":
    asyncio.run(main())
