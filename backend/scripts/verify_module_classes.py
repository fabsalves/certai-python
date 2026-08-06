"""End-to-end checks for multiple professors per module (requires seeded DB).

Usage (from backend/ with venv active):
  python scripts/verify_module_classes.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from unittest.mock import patch

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.context_builder import ContextBuilder
from app.core.database import SessionLocal
from app.models.assessment import CohortLessonNote
from app.models.cohort import (
    Cohort,
    CohortModuleProfessor,
    CohortModuleStudent,
    CohortProgress,
    Enrollment,
)
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.models.track import Module, Track
from app.models.user import Role, User
from app.services.cohort import ModuleClassService
from app.services.lesson_completion_service import complete_lesson
from app.services.track_structure import ordered_active_lessons


async def _load() -> tuple:
    async with SessionLocal() as db:
        cohort = await db.scalar(select(Cohort).limit(1))
        if cohort is None:
            raise RuntimeError("Nenhuma turma — rode bin/db-reset")

        track = await db.scalar(
            select(Track)
            .where(Track.id == cohort.track_id)
            .options(selectinload(Track.modules).selectinload(Module.lessons))
        )
        modules = sorted(track.modules, key=lambda m: m.position)
        fundamentos = modules[0]
        pratica = modules[1]
        lessons = await ordered_active_lessons(db, track.id)
        fund_lessons = [l for l in lessons if l.module_id == fundamentos.id]

        ana = await db.scalar(select(User).where(User.email == "prof@certai.app"))
        marcos = await db.scalar(
            select(User).where(User.email == "marcos.ferreira@certai.app")
        )
        mariana = await db.scalar(select(User).where(User.email == "aluno@certai.app"))
        eriko = await db.scalar(select(User).where(User.email == "eriko@certai.app"))
        pedro = await db.scalar(
            select(User).where(User.email == "pedro.almeida@certai.app")
        )
        if not all([ana, marcos, mariana, eriko, pedro]):
            raise RuntimeError("Usuários do seed ausentes — rode bin/db-reset")

        return (
            cohort.id,
            fundamentos.id,
            pratica.id,
            [l.id for l in fund_lessons],
            ana.id,
            marcos.id,
            mariana.id,
            eriko.id,
            pedro.id,
        )


async def _split_fundamentos(
    db,
    cohort_id,
    fundamentos_id,
    ana_id,
    marcos_id,
    mariana_id,
    eriko_id,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Make Fundamentos a two-professor module: Ana→Mariana, Marcos→Ériko."""
    existing = list(
        (
            await db.scalars(
                select(CohortModuleProfessor).where(
                    CohortModuleProfessor.cohort_id == cohort_id,
                    CohortModuleProfessor.module_id == fundamentos_id,
                )
            )
        ).all()
    )
    # Wipe prior progress/notes tied to these classes so the scenario is clean.
    class_ids = [c.id for c in existing]
    if class_ids:
        for note in (
            await db.scalars(
                select(CohortLessonNote).where(
                    CohortLessonNote.module_professor_id.in_(class_ids)
                )
            )
        ).all():
            await db.delete(note)
        for progress in (
            await db.scalars(
                select(CohortProgress).where(
                    CohortProgress.module_professor_id.in_(class_ids)
                )
            )
        ).all():
            await db.delete(progress)
        for roster in (
            await db.scalars(
                select(CohortModuleStudent).where(
                    CohortModuleStudent.module_professor_id.in_(class_ids)
                )
            )
        ).all():
            await db.delete(roster)
        await db.flush()

    ana_class = next((c for c in existing if c.professor_id == ana_id), None)
    if ana_class is None:
        ana_class = CohortModuleProfessor(
            cohort_id=cohort_id, module_id=fundamentos_id, professor_id=ana_id
        )
        db.add(ana_class)
        await db.flush()

    marcos_class = next((c for c in existing if c.professor_id == marcos_id), None)
    if marcos_class is None:
        marcos_class = CohortModuleProfessor(
            cohort_id=cohort_id, module_id=fundamentos_id, professor_id=marcos_id
        )
        db.add(marcos_class)
        await db.flush()

    # Drop any leftover professors of this module (shouldn't happen on seed).
    for c in existing:
        if c.id not in (ana_class.id, marcos_class.id):
            await db.delete(c)
    await db.flush()

    await ModuleClassService.replace_module_roster(
        db,
        [ana_class, marcos_class],
        {
            ana_class.id: [mariana_id],
            marcos_class.id: [eriko_id],
        },
    )
    await db.flush()
    return ana_class.id, marcos_class.id


async def _clear_student_progress(db, cohort_id) -> None:
    rows = (
        await db.scalars(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort_id
            )
        )
    ).all()
    for row in rows:
        await db.delete(row)
    await db.flush()


async def test_single_professor_shortcut() -> None:
    (
        cohort_id,
        _fundamentos_id,
        pratica_id,
        _fund_lessons,
        _ana_id,
        marcos_id,
        mariana_id,
        eriko_id,
        _pedro_id,
    ) = await _load()

    async with SessionLocal() as db:
        classes = await ModuleClassService.classes_of_module(db, cohort_id, pratica_id)
        assert len(classes) == 1, "Prática deve ter um professor no seed"
        assert classes[0].professor_id == marcos_id

        unassigned = await ModuleClassService.unassigned_student_ids(
            db, cohort_id, pratica_id
        )
        assert unassigned == [], "módulo com 1 professor nunca tem aluno sem grupo"

        students = await ModuleClassService.student_ids_of(db, classes[0])
        assert set(students) == {mariana_id, eriko_id}, (
            "professor único recebe a turma inteira"
        )
        print("OK atalho professor único (sem roster)")


async def test_split_resolution_and_guard() -> None:
    (
        cohort_id,
        fundamentos_id,
        _pratica_id,
        _fund_lessons,
        ana_id,
        marcos_id,
        mariana_id,
        eriko_id,
        pedro_id,
    ) = await _load()

    async with SessionLocal() as db:
        ana_class_id, marcos_class_id = await _split_fundamentos(
            db, cohort_id, fundamentos_id, ana_id, marcos_id, mariana_id, eriko_id
        )

        # Enroll Pedro without assigning him — triggers the guard.
        already = await db.scalar(
            select(Enrollment.id).where(
                Enrollment.cohort_id == cohort_id,
                Enrollment.student_id == pedro_id,
            )
        )
        if already is None:
            db.add(Enrollment(cohort_id=cohort_id, student_id=pedro_id))
            await db.flush()

        unassigned = await ModuleClassService.unassigned_student_ids(
            db, cohort_id, fundamentos_id
        )
        assert pedro_id in unassigned, "Pedro matriculado sem grupo deve aparecer"

        resolved_m = await ModuleClassService.resolve_for_student(
            db, cohort_id, fundamentos_id, mariana_id
        )
        resolved_e = await ModuleClassService.resolve_for_student(
            db, cohort_id, fundamentos_id, eriko_id
        )
        assert resolved_m is not None and resolved_m.id == ana_class_id
        assert resolved_e is not None and resolved_e.id == marcos_class_id

        ana_students = await ModuleClassService.student_ids_of(
            db, await db.get(CohortModuleProfessor, ana_class_id)
        )
        marcos_students = await ModuleClassService.student_ids_of(
            db, await db.get(CohortModuleProfessor, marcos_class_id)
        )
        assert ana_students == [mariana_id]
        assert marcos_students == [eriko_id]

        # Cleanup Pedro so later steps stay focused on the two-student split.
        enrollment = await db.scalar(
            select(Enrollment).where(
                Enrollment.cohort_id == cohort_id,
                Enrollment.student_id == pedro_id,
            )
        )
        if enrollment is not None:
            await db.delete(enrollment)
        await db.commit()
        print("OK divisão + resolução por aluno + guard de sem grupo")


async def test_completion_isolates_progress_and_context() -> None:
    (
        cohort_id,
        fundamentos_id,
        _pratica_id,
        fund_lessons,
        ana_id,
        marcos_id,
        mariana_id,
        eriko_id,
        _pedro_id,
    ) = await _load()

    lesson1, lesson2 = fund_lessons[0], fund_lessons[1]

    async with SessionLocal() as db:
        ana_class_id, marcos_class_id = await _split_fundamentos(
            db, cohort_id, fundamentos_id, ana_id, marcos_id, mariana_id, eriko_id
        )
        await _clear_student_progress(db, cohort_id)
        await db.commit()

    with patch(
        "app.services.lesson_completion_service.enqueue_after_commit",
        lambda *_a, **_k: None,
    ):
        async with SessionLocal() as db:
            # Ana closes lesson 1 — only Mariana is DISPARADA.
            note_a1 = await complete_lesson(
                db,
                cohort_id,
                lesson1,
                "Relato da Ana aula 1 — só a turma dela",
                module_professor_id=ana_class_id,
            )
            # Mark ingestion done so ContextBuilder includes the note.
            note_a1.ingestion_status = "done"
            note_a1.summary = "Resumo exclusivo da Ana"
            note_a1.unclear_points = "Pontos da Ana"
            await db.commit()

            mariana_prog = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.student_id == mariana_id,
                    StudentLessonProgress.lesson_id == lesson1,
                )
            )
            eriko_prog = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.student_id == eriko_id,
                    StudentLessonProgress.lesson_id == lesson1,
                )
            )
            assert mariana_prog is not None
            assert mariana_prog.status == StudentLessonProgressStatus.DISPARADA
            assert eriko_prog is None, "Ériko não pode receber DISPARADA da Ana"

            # CohortProgress only for Ana's class.
            ana_progress = await db.scalar(
                select(CohortProgress).where(
                    CohortProgress.cohort_id == cohort_id,
                    CohortProgress.lesson_id == lesson1,
                    CohortProgress.module_professor_id == ana_class_id,
                )
            )
            marcos_progress = await db.scalar(
                select(CohortProgress).where(
                    CohortProgress.cohort_id == cohort_id,
                    CohortProgress.lesson_id == lesson1,
                    CohortProgress.module_professor_id == marcos_class_id,
                )
            )
            assert ana_progress is not None
            assert marcos_progress is None

            # Context isolation.
            builder = ContextBuilder(db)
            bundle_m = await builder.build_lesson(
                cohort_id, lesson1, student_id=mariana_id
            )
            bundle_e = await builder.build_lesson(
                cohort_id, lesson1, student_id=eriko_id
            )
            assert any(
                n.get("summary") == "Resumo exclusivo da Ana"
                for n in bundle_m.cohort_notes
            ), "Mariana deve ver o relato da Ana"
            assert not any(
                n.get("summary") == "Resumo exclusivo da Ana"
                for n in bundle_e.cohort_notes
            ), "Ériko NÃO pode ver o relato da Ana"
            unlocked_m = {item["lesson_id"] for item in bundle_m.track_map if item["unlocked"]}
            unlocked_e = {item["lesson_id"] for item in bundle_e.track_map if item["unlocked"]}
            assert str(lesson1) in unlocked_m
            assert str(lesson1) not in unlocked_e
            print("OK encerramento A isola progresso + contexto")

            # Ana advances to lesson 2 without Marcos closing lesson 1.
            await complete_lesson(
                db,
                cohort_id,
                lesson2,
                "Relato da Ana aula 2",
                module_professor_id=ana_class_id,
            )
            await db.commit()

            eriko_l1 = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.student_id == eriko_id,
                    StudentLessonProgress.lesson_id == lesson1,
                )
            )
            assert eriko_l1 is None, (
                "avanço da Ana não pode criar ENCERRADA_POR_AVANCO no grupo do Marcos"
            )

            mariana_l1 = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.student_id == mariana_id,
                    StudentLessonProgress.lesson_id == lesson1,
                )
            )
            assert mariana_l1 is not None
            assert (
                mariana_l1.status == StudentLessonProgressStatus.ENCERRADA_POR_AVANCO
            ), "aula anterior da própria turma da Ana fecha por avanço"
            print("OK avanço da Ana não fecha a janela do Marcos")

            # Marcos closes lesson 1 afterwards — Ériko finally gets DISPARADA.
            note_m1 = await complete_lesson(
                db,
                cohort_id,
                lesson1,
                "Relato do Marcos aula 1 — só a turma dele",
                module_professor_id=marcos_class_id,
            )
            note_m1.ingestion_status = "done"
            note_m1.summary = "Resumo exclusivo do Marcos"
            await db.commit()

            eriko_l1 = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.student_id == eriko_id,
                    StudentLessonProgress.lesson_id == lesson1,
                )
            )
            assert eriko_l1 is not None
            assert eriko_l1.status == StudentLessonProgressStatus.DISPARADA

            bundle_e2 = await builder.build_lesson(
                cohort_id, lesson1, student_id=eriko_id
            )
            assert any(
                n.get("summary") == "Resumo exclusivo do Marcos"
                for n in bundle_e2.cohort_notes
            )
            assert not any(
                n.get("summary") == "Resumo exclusivo da Ana"
                for n in bundle_e2.cohort_notes
            ), "relato da Ana continua fora do bundle do Ériko"
            print("OK Marcos encerra depois e isola o próprio relato")


async def test_dispatch_targets_own_class_only() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from app.core.config import settings
    from app.services.whatsapp import dispatch_service

    (
        cohort_id,
        fundamentos_id,
        _pratica_id,
        fund_lessons,
        ana_id,
        marcos_id,
        mariana_id,
        eriko_id,
        _pedro_id,
    ) = await _load()
    lesson1 = fund_lessons[0]

    async with SessionLocal() as db:
        ana_class_id, _marcos_class_id = await _split_fundamentos(
            db, cohort_id, fundamentos_id, ana_id, marcos_id, mariana_id, eriko_id
        )
        await db.commit()

        phones: list[str] = []

        def fake_send(**kwargs):
            phones.append(kwargs["to_phone"])
            return "msg-id"

        with (
            patch.object(settings, "WHATSAPP_INVITE_USE_VOICE_TEMPLATE", False),
            patch.object(settings, "WHATSAPP_INVITE_TEMPLATE", "certai_convite"),
            patch.object(settings, "WHATSAPP_TEMPLATE_LANG", "pt_BR"),
            patch(
                "app.services.whatsapp.dispatch_service.send_template_message",
                side_effect=fake_send,
            ),
            patch(
                "app.services.whatsapp.dispatch_service._already_dispatched",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.whatsapp.dispatch_service.record_message",
                new=AsyncMock(),
            ),
            patch(
                "app.services.whatsapp.dispatch_service.get_or_create_conversation",
                new=AsyncMock(return_value=MagicMock(id=uuid.uuid4())),
            ),
        ):
            result = await dispatch_service.dispatch_lesson_invites(
                db, cohort_id, lesson1, ana_class_id
            )

        assert result["sent"] == 1, result
        # Only Mariana (Ana's class). Ériko's phone must not appear.
        mariana = await db.get(User, mariana_id)
        eriko = await db.get(User, eriko_id)
        assert phones == [mariana.whatsapp]
        assert eriko.whatsapp not in phones
        print("OK disparo WhatsApp só para a turma do professor")


async def main() -> None:
    await test_single_professor_shortcut()
    await test_split_resolution_and_guard()
    await test_completion_isolates_progress_and_context()
    await test_dispatch_targets_own_class_only()
    print("")
    print("verify_module_classes: OK — regras de turma por professor respeitadas")


if __name__ == "__main__":
    asyncio.run(main())
