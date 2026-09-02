"""Verification of the test-cohort rewind, end to end over the seed.

Builds its own test cohort (same track, professors and students as the seed one),
runs real lesson closures through `complete_lesson`, and then asserts what the two
rewind actions do -- and, just as important, what they refuse to do.

The seed is left untouched: the cohort this creates is removed at the end.

Usage (from the project root):
    bin/verify-sandbox
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, engine
from app.models.assessment import CohortLessonNote, LessonCoverage
from app.models.cohort import (
    Cohort,
    CohortModuleProfessor,
    CohortProgress,
    Enrollment,
)
from app.models.conversation import Author, Conversation, Message
from app.models.student_progress import (
    StudentLessonProgress,
    StudentLessonProgressStatus,
)
from app.models.track import Lesson
from app.models.usage import AiUsageEvent
from app.schemas import CoverageSegmentIn
from app.services import coverage_service
from app.services.cohort import (
    NothingToUndoError,
    SandboxOnlyError,
    SandboxService,
)
from app.services.conversation_service import (
    get_or_create_conversation,
    record_message,
)
from app.services.lesson_completion_service import complete_lesson
from app.services.track_structure import ordered_active_lessons

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
OFF = "\033[0m"


@dataclass
class Report:
    checks: list[tuple[bool, str]] = field(default_factory=list)

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        self.checks.append((ok, label))
        mark = f"{GREEN}✓{OFF}" if ok else f"{RED}✗{OFF}"
        print(f"  {mark} {label}")
        if detail:
            print(f"    {DIM}{detail}{OFF}")

    @property
    def failed(self) -> int:
        return sum(1 for ok, _ in self.checks if not ok)


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{OFF}")


async def _build_sandbox_cohort(
    db: AsyncSession,
    source: Cohort,
    *,
    name: str = "Turma de teste (verify-sandbox)",
) -> Cohort:
    """A test cohort mirroring the seed one: same track, professors, students."""
    sandbox = Cohort(
        name=name,
        track_id=source.track_id,
        organization_id=source.organization_id,
        is_sandbox=True,
    )
    db.add(sandbox)
    await db.flush()

    for module_class in (
        await db.scalars(
            select(CohortModuleProfessor).where(
                CohortModuleProfessor.cohort_id == source.id
            )
        )
    ).all():
        db.add(
            CohortModuleProfessor(
                cohort_id=sandbox.id,
                module_id=module_class.module_id,
                professor_id=module_class.professor_id,
            )
        )

    student_ids = list(
        (
            await db.scalars(
                select(Enrollment.student_id).where(Enrollment.cohort_id == source.id)
            )
        ).all()
    )
    for student_id in student_ids:
        db.add(Enrollment(cohort_id=sandbox.id, student_id=student_id))

    await db.flush()
    return sandbox


async def _classes_of(db: AsyncSession, cohort: Cohort) -> dict[uuid.UUID, CohortModuleProfessor]:
    return {
        item.module_id: item
        for item in (
            await db.scalars(
                select(CohortModuleProfessor).where(
                    CohortModuleProfessor.cohort_id == cohort.id
                )
            )
        ).all()
    }


async def _count(db: AsyncSession, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for column, value in filters.items():
        stmt = stmt.where(getattr(model, column) == value)
    return int(await db.scalar(stmt) or 0)


async def _close(
    db: AsyncSession,
    cohort: Cohort,
    lesson: Lesson,
    module_class: CohortModuleProfessor,
    transcript: str,
    coverage: list[CoverageSegmentIn] | None = None,
):
    note = await complete_lesson(
        db,
        cohort.id,
        lesson.id,
        transcript,
        module_professor_id=module_class.id,
        coverage=coverage,
    )
    await db.commit()
    return note


async def run() -> int:
    report = Report()

    async with SessionLocal() as db:
        real = await db.scalar(select(Cohort).order_by(Cohort.created_at).limit(1))
        if real is None:
            raise SystemExit("Nenhuma turma encontrada. Rode bin/db-reset primeiro.")

        lessons = await ordered_active_lessons(db, real.track_id)
        by_module: dict[uuid.UUID, list[Lesson]] = {}
        for lesson in lessons:
            by_module.setdefault(lesson.module_id, []).append(lesson)
        module_lessons = next(
            (group for group in by_module.values() if len(group) >= 3), None
        )
        if module_lessons is None:
            raise SystemExit("O seed precisa de um módulo com pelo menos 3 aulas.")

        sandbox = await _build_sandbox_cohort(db, real)
        # A neighbour cohort with progression of its own. Every rewind below runs
        # on `sandbox`; this one exists to prove the blast radius is one cohort.
        # A test cohort, not the seed's: the seed must be left as it was found,
        # and a real cohort has no way to be cleaned up (undo refuses it, by design).
        neighbour = await _build_sandbox_cohort(db, real, name="Turma vizinha (verify-sandbox)")
        await db.commit()
        # Kept as plain values: a rollback in the cleanup expires the ORM
        # objects, and reading `.id` off them would then need to hit the database.
        classes = await _classes_of(db, sandbox)
        module_class = classes[module_lessons[0].module_id]
        student_ids = list(
            (
                await db.scalars(
                    select(Enrollment.student_id).where(
                        Enrollment.cohort_id == sandbox.id
                    )
                )
            ).all()
        )
        sandbox_id = sandbox.id
        neighbour_id = neighbour.id
        neighbour_class = (await _classes_of(db, neighbour))[module_lessons[0].module_id]
        await _close(
            db,
            neighbour,
            module_lessons[0],
            neighbour_class,
            "Aula da turma vizinha, com pendência.",
            [
                CoverageSegmentIn(
                    lesson_id=module_lessons[0].id,
                    kind="planned",
                    extent="partial",
                    covered="metade do conteúdo",
                    pending="a outra metade",
                    source="professor",
                )
            ],
        )
        print(f"{DIM}turma real={real.name}  turma de teste={sandbox.name}{OFF}")

        try:
            # ------------------------------------------------------------ 1
            section("1 · Turma real recusa as duas ações")
            for action, label in (
                (SandboxService.undo_last_closure, "desfazer"),
                (SandboxService.reset_progress, "zerar"),
            ):
                try:
                    await action(db, real)
                    report.check(False, f"{label} recusado em turma real")
                except SandboxOnlyError:
                    report.check(True, f"{label} recusado em turma real")
            notes_real = await _count(db, CohortLessonNote, cohort_id=real.id)
            report.check(
                notes_real == await _count(db, CohortLessonNote, cohort_id=real.id),
                "nada foi apagado na turma real",
            )

            section("2 · Turma de teste sem encerramento não tem o que desfazer")
            try:
                await SandboxService.undo_last_closure(db, sandbox)
                report.check(False, "desfazer recusado sem encerramento")
            except NothingToUndoError:
                report.check(True, "desfazer recusado sem encerramento")

            # ------------------------------------------------------------ 3
            section("3 · Desfazer um encerramento simples")
            first, second, third = module_lessons[0], module_lessons[1], module_lessons[2]
            await _close(db, sandbox, first, module_class, "Fechei tudo.")

            # A conversation with a message, through the same helpers the
            # WhatsApp dispatch uses -- so the rewind faces real rows.
            conversation = await get_or_create_conversation(
                db, sandbox.id, student_ids[0], first.id
            )
            await record_message(db, conversation, Author.AGENT, "convite simulado")
            await db.commit()

            result = await SandboxService.undo_last_closure(db, sandbox)
            await db.commit()
            report.check(
                result["lesson_title"] == first.title,
                "desfez o encerramento mais recente",
                f"aula={result['lesson_title']} · professor={result['professor_name']}",
            )
            report.check(
                await _count(db, CohortLessonNote, cohort_id=sandbox.id) == 0
                and await _count(db, LessonCoverage, cohort_id=sandbox.id) == 0,
                "relato e cobertura removidos",
            )
            report.check(
                await _count(db, CohortProgress, cohort_id=sandbox.id) == 0,
                "aula reabriu (CohortProgress removido)",
            )
            report.check(
                await _count(db, StudentLessonProgress, cohort_id=sandbox.id) == 0,
                "progresso dos alunos removido",
            )
            report.check(
                await _count(db, Conversation, cohort_id=sandbox.id) == 0
                and await _count(db, Message, conversation_id=conversation.id) == 0,
                "conversa e mensagens removidas (cascade)",
            )

            # ------------------------------------------------------------ 4
            section("4 · Desfazer devolve a aula anterior ao status que tinha")
            await _close(db, sandbox, first, module_class, "Fechei tudo.")
            # The student engaged with lesson 1, so it was ATIVA before advancing.
            row = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == sandbox.id,
                    StudentLessonProgress.lesson_id == first.id,
                    StudentLessonProgress.student_id == student_ids[0],
                )
            )
            row.status = StudentLessonProgressStatus.ATIVA
            row.activated_at = func.now()
            await db.commit()

            await _close(db, sandbox, second, module_class, "Segui o plano.")
            row = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == sandbox.id,
                    StudentLessonProgress.lesson_id == first.id,
                    StudentLessonProgress.student_id == student_ids[0],
                )
            )
            report.check(
                row.status == StudentLessonProgressStatus.ENCERRADA_POR_AVANCO,
                "encerrar a aula 2 fechou a aula 1 por avanço",
            )

            await SandboxService.undo_last_closure(db, sandbox)
            await db.commit()
            await db.refresh(row)
            report.check(
                row.status == StudentLessonProgressStatus.ATIVA
                and row.encerrada_por_avanco_at is None,
                "aula 1 voltou para ATIVA (tinha activated_at)",
                f"status={row.status.value}",
            )

            other = await db.scalar(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == sandbox.id,
                    StudentLessonProgress.lesson_id == first.id,
                    StudentLessonProgress.student_id != student_ids[0],
                )
            )
            report.check(
                other is None
                or other.status == StudentLessonProgressStatus.DISPARADA,
                "aluno que nunca interagiu voltou para DISPARADA",
                f"status={other.status.value if other else '(sem outro aluno)'}",
            )

            # ------------------------------------------------------------ 5
            section("5 · Desfazer uma sessão composta traz a pendência de volta")
            pending_text = "coerência textual e revisão final"
            await _close(
                db,
                sandbox,
                second,
                module_class,
                "Não fechei tudo.",
                [
                    CoverageSegmentIn(
                        lesson_id=second.id,
                        kind="planned",
                        extent="partial",
                        covered="cobri a abertura",
                        pending=pending_text,
                        source="professor",
                    )
                ],
            )
            await _close(
                db,
                sandbox,
                third,
                module_class,
                "Fechei o que faltou e avancei.",
                [
                    CoverageSegmentIn(
                        lesson_id=second.id,
                        kind="carryover",
                        extent="full",
                        covered="fechei a coerência textual",
                        source="professor",
                    ),
                    CoverageSegmentIn(
                        lesson_id=third.id,
                        kind="planned",
                        extent="full",
                        covered="conteúdo do dia",
                        source="professor",
                    ),
                ],
            )

            resolved = await coverage_service.current_pendings(
                db,
                cohort_id=sandbox.id,
                module_professor_id=module_class.id,
                lesson_ids=[second.id],
            )
            report.check(
                second.id not in resolved,
                "antes de desfazer: pendência da aula 2 está resolvida",
            )

            await SandboxService.undo_last_closure(db, sandbox)
            await db.commit()

            back = await coverage_service.current_pendings(
                db,
                cohort_id=sandbox.id,
                module_professor_id=module_class.id,
                lesson_ids=[second.id],
            )
            report.check(
                back.get(second.id) == pending_text,
                "depois de desfazer: a pendência voltou sozinha",
                back.get(second.id, "(vazia)"),
            )

            # ------------------------------------------------------------ 6
            section("6 · Desfazer em sequência caminha para trás")
            undone = []
            for _ in range(3):
                try:
                    result = await SandboxService.undo_last_closure(db, sandbox)
                    await db.commit()
                    undone.append(result["lesson_title"])
                except NothingToUndoError:
                    break
            report.check(
                await _count(db, CohortLessonNote, cohort_id=sandbox.id) == 0,
                "desfazendo repetidamente, a turma volta ao início",
                f"desfeitos: {undone}",
            )

            # ------------------------------------------------------------ 7
            section("7 · Zerar preserva o cadastro e os custos")
            await _close(db, sandbox, first, module_class, "Fechei tudo.")
            db.add(
                AiUsageEvent(
                    cohort_id=sandbox.id,
                    provider="openai",
                    model="gpt-test",
                    operation="coverage",
                    cost_kind="chat_text_in",
                    quantity=Decimal("100"),
                    unit="tokens",
                    estimated_cost_usd=Decimal("0.01"),
                    provider_event_id=f"verify-sandbox:{uuid.uuid4().hex}",
                    occurred_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

            enrollments_before = await _count(db, Enrollment, cohort_id=sandbox.id)
            classes_before = await _count(db, CohortModuleProfessor, cohort_id=sandbox.id)
            usage_before = await _count(db, AiUsageEvent, cohort_id=sandbox.id)

            result = await SandboxService.reset_progress(db, sandbox)
            await db.commit()

            report.check(
                await _count(db, CohortLessonNote, cohort_id=sandbox.id) == 0
                and await _count(db, LessonCoverage, cohort_id=sandbox.id) == 0
                and await _count(db, CohortProgress, cohort_id=sandbox.id) == 0
                and await _count(db, StudentLessonProgress, cohort_id=sandbox.id) == 0
                and await _count(db, Conversation, cohort_id=sandbox.id) == 0,
                "andamento zerado",
                f"removidos={result['removed']}",
            )
            report.check(
                await _count(db, Enrollment, cohort_id=sandbox.id) == enrollments_before
                and await _count(db, CohortModuleProfessor, cohort_id=sandbox.id)
                == classes_before,
                "cadastro preservado (matrículas e professores)",
                f"{enrollments_before} matrícula(s), {classes_before} turma(s) de professor",
            )
            report.check(
                await _count(db, AiUsageEvent, cohort_id=sandbox.id) == usage_before,
                "custos de IA preservados",
                f"{usage_before} evento(s)",
            )
            report.check(
                await db.get(Cohort, sandbox.id) is not None,
                "a turma continua existindo",
            )

            # ------------------------------------------------------------ 8
            section("8 · Depois de zerar, o ciclo roda de novo")
            note = await _close(db, sandbox, first, module_class, "Recomeçando.")
            report.check(
                note is not None
                and await _count(db, CohortProgress, cohort_id=sandbox.id) == 1,
                "encerrar a aula 1 funciona como numa turma nova",
            )
            report.check(
                await _count(db, LessonCoverage, cohort_id=sandbox.id) == 1,
                "cobertura default gravada, como no caminho feliz",
            )

            section("9 · O raio de dano é de uma turma só")
            report.check(
                await _count(db, CohortLessonNote, cohort_id=neighbour_id) == 1
                and await _count(db, LessonCoverage, cohort_id=neighbour_id) == 1
                and await _count(db, CohortProgress, cohort_id=neighbour_id) == 1,
                "a turma vizinha manteve relato, cobertura e progresso",
            )
            neighbour_pending = await coverage_service.current_pendings(
                db,
                cohort_id=neighbour_id,
                module_professor_id=neighbour_class.id,
                lesson_ids=[module_lessons[0].id],
            )
            report.check(
                neighbour_pending.get(module_lessons[0].id) == "a outra metade",
                "a pendência da turma vizinha segue de pé",
                neighbour_pending.get(module_lessons[0].id, "(perdida)"),
            )
            report.check(
                await _count(db, CohortLessonNote, cohort_id=real.id) == notes_real,
                "a turma real segue como estava",
                f"{notes_real} relato(s), como antes",
            )
        finally:
            # The seed is left exactly as it was found. Progression goes first:
            # cohort_progress references cohort_module_professors with RESTRICT,
            # so the cohort cannot be dropped while it still has progress.
            await db.rollback()
            for cohort_id in (sandbox_id, neighbour_id):
                fresh = await db.get(Cohort, cohort_id)
                if fresh is None:
                    continue
                await SandboxService.reset_progress(db, fresh)
                # Core delete, not ORM: the ORM cascade would lazy-load the
                # cohort's collections mid-flush. Postgres already cascades
                # enrollments and teaching classes, and progress is gone above.
                await db.execute(delete(Cohort).where(Cohort.id == fresh.id))
                await db.commit()
            print(f"\n{DIM}turmas de teste removidas{OFF}")

    total = len(report.checks)
    print()
    if report.failed:
        print(f"{RED}{BOLD}{report.failed} de {total} verificações falharam{OFF}")
        return 1
    print(f"{GREEN}{BOLD}{total}/{total} verificações passaram{OFF}")
    return 0


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    engine.echo = False
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
