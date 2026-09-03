"""Verification of the lesson-dynamism package, end to end over the seed.

Runs the three real-world scenarios of the product doc plus the happy path, and
asserts what actually got registered: coverage rows, the context bundle the
student's AI receives, and the scope the evaluator is asked to judge.

Deterministic by design: the professor's confirmed coverage is injected the same
way the UI submits it, so no LLM call is needed and every run gives the same
result. `--with-ai` additionally exercises the AI proposal itself (needs
OPENAI_API_KEY) and prints what it derived.

Usage (from the project root):
    bin/verify-dinamismo
    bin/verify-dinamismo --with-ai

Assumes a freshly seeded database (`bin/db-reset`): it closes lessons, which
advances the cohort.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import ContextBuilder
from app.core.database import SessionLocal, engine
from app.models.assessment import CoverageKind, LessonCoverage
from app.models.cohort import Cohort, CohortModuleProfessor, CohortProgress, Enrollment
from app.models.track import Lesson
from app.models.user import User
from app.schemas import CoverageSegmentIn
from app.services import coverage_service
from app.services.assessment import lesson_assessment_service as assess_mod
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


async def _seed_context(db: AsyncSession):
    """The seed cohort, its lessons in order, and the class of each module."""
    cohort = await db.scalar(select(Cohort).order_by(Cohort.created_at).limit(1))
    if cohort is None:
        raise SystemExit("Nenhuma turma encontrada. Rode bin/db-reset primeiro.")

    lessons = await ordered_active_lessons(db, cohort.track_id)
    if len(lessons) < 4:
        raise SystemExit("A trilha do seed precisa de pelo menos 4 aulas.")

    classes = {
        module_class.module_id: module_class
        for module_class in (
            await db.scalars(
                select(CohortModuleProfessor).where(
                    CohortModuleProfessor.cohort_id == cohort.id
                )
            )
        ).all()
    }
    student_id = await db.scalar(
        select(Enrollment.student_id).where(Enrollment.cohort_id == cohort.id).limit(1)
    )
    if student_id is None:
        raise SystemExit("Nenhum aluno matriculado na turma do seed.")
    return cohort, lessons, classes, student_id


async def _coverage_rows(
    db: AsyncSession, cohort_id: uuid.UUID, lesson_id: uuid.UUID
) -> list[LessonCoverage]:
    return list(
        (
            await db.scalars(
                select(LessonCoverage)
                .where(
                    LessonCoverage.cohort_id == cohort_id,
                    LessonCoverage.lesson_id == lesson_id,
                )
                .order_by(LessonCoverage.created_at)
            )
        ).all()
    )


async def _close(
    db: AsyncSession,
    cohort: Cohort,
    lesson: Lesson,
    module_class: CohortModuleProfessor,
    transcript: str,
    coverage: list[CoverageSegmentIn] | None,
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


async def _bundle_blocks(
    db: AsyncSession, cohort_id: uuid.UUID, lesson_id: uuid.UUID, student_id: uuid.UUID
) -> tuple[str, list[dict]]:
    bundle = await ContextBuilder(db).build_lesson(
        cohort_id, lesson_id, student_id=student_id
    )
    return bundle.to_system_blocks(), bundle.taught_scope


async def run(with_ai: bool) -> int:
    report = Report()

    async with SessionLocal() as db:
        cohort, lessons, classes, student_id = await _seed_context(db)
        student = await db.get(User, student_id)
        print(f"{DIM}turma={cohort.name}  aluno={student.name if student else '?'}{OFF}")

        # Coverage is per teaching class, and a class only ever covers lessons of
        # its own module -- so the scenarios run inside one module each, the way
        # a real professor lives them.
        by_module: dict[uuid.UUID, list[Lesson]] = {}
        for lesson in lessons:
            by_module.setdefault(lesson.module_id, []).append(lesson)
        groups = [group for group in by_module.values() if len(group) >= 3]
        if not groups:
            raise SystemExit("O seed precisa de um módulo com pelo menos 3 aulas.")
        first = groups[0]
        second = groups[1] if len(groups) > 1 else None
        class_a = classes[first[0].module_id]
        print(
            f"{DIM}módulo A: {', '.join(item.title for item in first[:3])}{OFF}"
        )

        # ---------------------------------------------------------------- 1
        section("1 · Caminho feliz (regressão) — aula conforme o plano")
        plain = first[0]
        await _close(
            db, cohort, plain, class_a, "Fechamos todo o conteúdo previsto.", None
        )

        rows = await _coverage_rows(db, cohort.id, plain.id)
        report.check(
            len(rows) == 1
            and rows[0].kind == CoverageKind.PLANNED
            and rows[0].extent.value == "full"
            and not rows[0].pending,
            "uma cobertura (âncora, planned, full) e nada pendente",
            f"{len(rows)} linha(s)",
        )
        report.check(
            await db.scalar(
                select(CohortProgress).where(
                    CohortProgress.cohort_id == cohort.id,
                    CohortProgress.lesson_id == plain.id,
                )
            )
            is not None,
            "turma avançou (CohortProgress criado)",
        )

        blocks, taught = await _bundle_blocks(db, cohort.id, plain.id, student_id)
        report.check(
            taught == [] and "actually taught" not in blocks,
            "bundle sem bloco de escopo ministrado — idêntico ao pré-mudança",
        )
        report.check(
            "(a sessão seguiu o conteúdo planejado da aula)"
            in assess_mod._format_taught_scope(taught),
            "avaliador informado de que a aula seguiu o plano",
        )

        # The AI proposal describes the lesson even when nothing deviated, so the
        # happy path arrives here with `covered` filled. Persisting that text
        # would put a paraphrase in the bundle, declared as the authority above
        # the lesson's own material. It has to be stored bare.
        section("1b · Caminho feliz com descrição da IA")
        described = second[0] if second else None
        if described is None:
            report.check(True, "pulado (seed sem segundo módulo)")
        else:
          await _close(
            db,
            cohort,
            described,
            classes[described.module_id],
            "Fechei todo o conteúdo previsto da aula.",
            [
                CoverageSegmentIn(
                    lesson_id=described.id,
                    kind="planned",
                    extent="full",
                    covered="Os alunos revisaram o parecer de um colega.",
                    source="ai",
                )
            ],
          )
          rows = await _coverage_rows(db, cohort.id, described.id)
          report.check(
            len(rows) == 1 and not rows[0].covered,
            "descrição sem informação nova não é persistida",
            f"covered={rows[0].covered!r}" if rows else "(sem linha)",
          )
          blocks, taught = await _bundle_blocks(db, cohort.id, described.id, student_id)
          report.check(
            taught == [] and "actually taught" not in blocks,
            "bundle segue sem o bloco, como no caminho feliz",
          )

        # ---------------------------------------------------------------- 2
        section("2 · Aula incompleta — encerrada antes do ponto planejado")
        incomplete = first[1]
        pending_text = "coerência textual e revisão do parágrafo final"
        await _close(
            db,
            cohort,
            incomplete,
            class_a,
            "Não fechei o conteúdo previsto; encerrei antes.",
            [
                CoverageSegmentIn(
                    lesson_id=incomplete.id,
                    kind="planned",
                    extent="partial",
                    covered="cobri só a abertura do parecer",
                    pending=pending_text,
                    source="professor",
                )
            ],
        )

        pendings = await coverage_service.current_pendings(
            db,
            cohort_id=cohort.id,
            module_professor_id=class_a.id,
            lesson_ids=[incomplete.id],
        )
        report.check(
            pendings.get(incomplete.id) == pending_text,
            "pendência vigente registrada na aula",
            pendings.get(incomplete.id, "(vazia)"),
        )
        report.check(
            await db.scalar(
                select(CohortProgress).where(
                    CohortProgress.cohort_id == cohort.id,
                    CohortProgress.lesson_id == incomplete.id,
                )
            )
            is not None,
            "turma avançou mesmo com a aula incompleta",
        )

        blocks, taught = await _bundle_blocks(db, cohort.id, incomplete.id, student_id)
        report.check(
            "actually taught" in blocks and pending_text in blocks,
            "bundle traz o escopo ministrado e marca o pendente",
        )
        report.check(
            all(item["origin"] == "planned" for item in taught),
            "nenhum segmento espúrio no escopo da sessão",
        )
        report.check(
            f"NÃO ministrado ao aluno: {pending_text}"
            in assess_mod._format_taught_scope(taught),
            "avaliador recebe o pendente como não ministrado",
        )
        closure = assess_mod._lesson_closure_block(
            None, message_count=0, score_count=0, pending=pending_text
        )
        report.check(
            "não lacuna deste aluno" in closure and pending_text in closure,
            "avaliador instruído a não rebaixar o aluno pelo pendente",
        )

        # ---------------------------------------------------------------- 3
        section("3 · Aula composta — fecha a pendência da anterior e avança")
        composed = first[2]
        carryover_text = "fechamos coerência textual, que faltou da aula anterior"
        window = await coverage_service.candidate_window(
            db, cohort.id, composed.id, module_professor_id=class_a.id
        )
        report.check(
            incomplete.id in {item.id for item in window},
            "a aula com pendência entra na janela de candidatas",
            f"{[item.title for item in window]}",
        )

        await _close(
            db,
            cohort,
            composed,
            class_a,
            "Começamos fechando o que faltou e depois avançamos no conteúdo do dia.",
            [
                CoverageSegmentIn(
                    lesson_id=incomplete.id,
                    kind="carryover",
                    extent="full",
                    covered=carryover_text,
                    source="professor",
                ),
                CoverageSegmentIn(
                    lesson_id=composed.id,
                    kind="planned",
                    extent="partial",
                    covered="avançamos no conteúdo do dia",
                    pending="a última prática",
                    source="professor",
                ),
            ],
        )

        blocks, taught = await _bundle_blocks(db, cohort.id, composed.id, student_id)
        origins = {item["origin"] for item in taught}
        report.check(
            origins == {"carryover", "planned"},
            "uma conversa só, na âncora, com os dois blocos e suas origens",
            f"origens={sorted(origins)}",
        )
        report.check(
            carryover_text in blocks,
            "a cauda da aula anterior é cobrada na conversa desta aula",
        )

        # ---------------------------------------------------------------- 4
        section("4 · Pendência resolvida — a aula anterior não deve mais nada")
        pendings = await coverage_service.current_pendings(
            db,
            cohort_id=cohort.id,
            module_professor_id=class_a.id,
            lesson_ids=[incomplete.id],
        )
        report.check(
            incomplete.id not in pendings,
            "pendência se resolveu sem UPDATE (append-only)",
        )
        report.check(
            await coverage_service.own_pendency(
                db,
                cohort_id=cohort.id,
                module_professor_id=class_a.id,
                lesson_id=incomplete.id,
            )
            == pending_text,
            "histórico preservado: a própria sessão ainda declara o que faltou",
        )
        carryover = await coverage_service.later_carryover(
            db,
            cohort_id=cohort.id,
            module_professor_id=class_a.id,
            lesson_id=incomplete.id,
        )
        report.check(
            carryover is not None and carryover["delivered_in"] == composed.title,
            "avaliador da aula sabe onde a evidência foi colhida",
            f"delivered_in={carryover['delivered_in'] if carryover else None}",
        )
        closure = assess_mod._lesson_closure_block(
            None, message_count=0, score_count=0, carryover=carryover
        )
        report.check(
            composed.title in closure and "gaps" in closure,
            "closure block aponta a sessão que entregou o conteúdo",
        )

        # ---------------------------------------------------------------- 5
        if second is None:
            section("5 · Aula adiantada — pulado (seed sem segundo módulo)")
        else:
            section("5 · Aula adiantada — avançou no conteúdo da aula seguinte")
            class_b = classes[second[0].module_id]
            ahead, next_lesson = second[1], second[2]
            advance_text = "adiantei o conceito de argumentação objetiva da aula seguinte"
            await _close(
                db,
                cohort,
                ahead,
                class_b,
                "A turma rendeu e avancei no conteúdo da aula seguinte.",
                [
                    CoverageSegmentIn(
                        lesson_id=ahead.id,
                        kind="planned",
                        extent="full",
                        covered="fechei todo o conteúdo do dia",
                        source="professor",
                    ),
                    CoverageSegmentIn(
                        lesson_id=next_lesson.id,
                        kind="advance",
                        extent="partial",
                        covered=advance_text,
                        pending="o restante da aula seguinte",
                        source="professor",
                    ),
                ],
            )

            rows_next = await _coverage_rows(db, cohort.id, next_lesson.id)
            report.check(
                len(rows_next) == 1 and rows_next[0].kind == CoverageKind.ADVANCE,
                "excedente guardado na aula seguinte como advance",
                f"{[row.kind.value for row in rows_next]}",
            )
            report.check(
                await db.scalar(
                    select(CohortProgress).where(
                        CohortProgress.cohort_id == cohort.id,
                        CohortProgress.lesson_id == next_lesson.id,
                    )
                )
                is None,
                "a aula seguinte NÃO foi liberada — sem segundo convite",
            )

            blocks, taught = await _bundle_blocks(db, cohort.id, ahead.id, student_id)
            report.check(
                advance_text in blocks,
                "o que foi adiantado chega ao aluno como texto do que foi dito",
            )
            report.check(
                bool(next_lesson.content.strip())
                and next_lesson.content.strip() not in blocks,
                "conteúdo planejado da aula seguinte continua FORA do bundle",
            )
            report.check(
                any(item["origin"] == "advance" for item in taught),
                "escopo da sessão identifica a origem do excedente",
            )

            # Isolation: the other class's pendency must never leak into this one.
            window_b = await coverage_service.candidate_window(
                db, cohort.id, ahead.id, module_professor_id=class_b.id
            )
            report.check(
                all(item.module_id == second[0].module_id for item in window_b),
                "janela restrita ao módulo da própria turma",
                f"{[item.title for item in window_b]}",
            )
            report.check(
                composed.id not in {item.id for item in window_b},
                "pendência de outra turma não entra nesta janela",
            )

        # ---------------------------------------------------------------- 5b
        section("5b · Fronteira de módulo")
        if second is None:
            report.check(True, "pulado (seed sem segundo módulo)")
        else:
            last_of_first = first[-1]
            # Different professors on the two modules: not recordable, but it must
            # be surfaced instead of dropped in silence.
            owners = await coverage_service.recordable_module_owners(
                db, cohort.id, class_a
            )
            report.check(
                second[0].module_id not in owners,
                "professor diferente: módulo vizinho fica fora do alcance",
                f"{len(owners)} módulo(s) no alcance",
            )
            blocked = await coverage_service.unrecordable_neighbours(
                db, cohort.id, last_of_first.id, module_professor_id=class_a.id
            )
            report.check(
                any(item[0].id == second[0].id for item in blocked),
                "a aula do outro professor é reportada como fora do alcance",
                f"{[(l.title, name) for l, name in blocked]}",
            )

            # Same professor on both modules: it is an ordinary deviation, and the
            # row belongs to the class that owns the lesson.
            other_class = classes[second[0].module_id]
            original_professor = other_class.professor_id
            other_class.professor_id = class_a.professor_id
            await db.commit()
            try:
                owners = await coverage_service.recordable_module_owners(
                    db, cohort.id, class_a
                )
                report.check(
                    owners.get(second[0].module_id) == other_class.id,
                    "mesmo professor: o módulo vizinho entra, sob a turma dona dele",
                )
                window = await coverage_service.candidate_window(
                    db, cohort.id, last_of_first.id, module_professor_id=class_a.id
                )
                report.check(
                    second[0].id in {item.id for item in window},
                    "a janela alcança a primeira aula do módulo seguinte",
                    f"{[item.title for item in window]}",
                )
                report.check(
                    not await coverage_service.unrecordable_neighbours(
                        db, cohort.id, last_of_first.id, module_professor_id=class_a.id
                    ),
                    "nada fora do alcance quando é o mesmo professor",
                )

                # A pendency left in the previous module is recorded under that
                # module's class. Anchored two lessons into the next module -- so
                # the plain neighbourhood cannot reach back that far -- the window
                # must still include it: a pendency does not expire at a boundary.
                owed = await coverage_service.current_pendings(
                    db,
                    cohort_id=cohort.id,
                    module_professor_id=class_a.id,
                    lesson_ids=[item.id for item in first],
                )
                anchored_next = await coverage_service.candidate_window(
                    db, cohort.id, second[1].id, module_professor_id=other_class.id
                )
                reached = {item.id for item in anchored_next}
                report.check(
                    bool(owed) and all(lesson_id in reached for lesson_id in owed),
                    "pendência do módulo anterior alcançada de dentro do seguinte",
                    f"deve={[first[i].title for i in range(len(first)) if first[i].id in owed]} "
                    f"janela={[item.title for item in anchored_next]}",
                )
            finally:
                other_class.professor_id = original_professor
                await db.commit()

        # ---------------------------------------------------------------- 6
        section("6 · Guardas")
        target = first[2] if second is None else second[1]
        target_class = classes[target.module_id]
        note = await _close(
            db,
            cohort,
            target,
            target_class,
            "Relato qualquer.",
            [
                CoverageSegmentIn(
                    lesson_id=plain.id,  # fora da janela desta turma
                    kind="carryover",
                    extent="full",
                    covered="não deveria entrar",
                    source="professor",
                )
            ],
        )
        rows = await _coverage_rows(db, cohort.id, plain.id)
        report.check(
            all(row.covered != "não deveria entrar" for row in rows),
            "segmento fora da janela é descartado, não persistido",
        )
        rows_note = list(
            (
                await db.scalars(
                    select(LessonCoverage).where(LessonCoverage.note_id == note.id)
                )
            ).all()
        )
        report.check(
            len(rows_note) == 1 and rows_note[0].lesson_id == note.lesson_id,
            "âncora sempre presente, mesmo com entrada inválida",
        )

        # ---------------------------------------------------------------- 7
        if with_ai:
            section("7 · Proposta pela IA (requer OPENAI_API_KEY)")
            proposal = await coverage_service.propose_coverage(
                db,
                cohort_id=cohort.id,
                module_professor_id=class_a.id,
                anchor_lesson_id=first[2].id,
                transcript=(
                    "Hoje comecei fechando o que faltou da aula anterior e depois "
                    "cobri só metade do conteúdo do dia. Não deu tempo do resto."
                ),
            )
            report.check(proposal.from_ai, "a IA respondeu")

            # A general rule ("stay inside the coverage") did not hold: summarising
            # the report is the model's main job, so it wrote down the advance the
            # professor mentioned. Naming the off-limits lesson does hold. Three
            # rounds, because one clean answer proves nothing about a prompt.
            from app.services.lesson_completion_service import consolidate_notes

            boundary = (
                "### Aula do dia\nsituação: coberta por completo\n"
                "ministrado: (sem detalhe)\n\n"
                "### Aulas que NÃO fazem parte desta sessão\n"
                '"Revisão em pares"\n'
                "São de outro professor. Mesmo que o relato as mencione, não "
                "escreva nada sobre elas em nenhum dos três campos, nem de "
                "passagem: estes alunos não as receberam."
            )
            leaked = 0
            for _ in range(3):
                out = await consolidate_notes(
                    "Fechei o rascunho e ainda adiantei a revisão em pares da "
                    "próxima aula.",
                    coverage_block=boundary,
                )
                if "pares" in " ".join(out.values()).lower():
                    leaked += 1
            report.check(
                leaked == 0,
                "consolidação não menciona a aula fora do alcance",
                f"{leaked} de 3 rodadas vazaram",
            )
            for segment in proposal.segments:
                print(
                    f"    {DIM}{segment.lesson_title} · {segment.kind} · "
                    f"{segment.extent}{OFF}"
                )
                print(f"      coberto: {segment.covered or '(vazio)'}")
                if segment.pending:
                    print(f"      pendente: {segment.pending}")
            report.check(
                any(item.lesson_id == first[2].id for item in proposal.segments),
                "âncora presente na proposta",
            )
            allowed = {item.lesson_id for item in proposal.candidates}
            report.check(
                all(item.lesson_id in allowed for item in proposal.segments),
                "nenhum segmento fora da janela",
            )

    total = len(report.checks)
    passed = total - report.failed
    print()
    if report.failed:
        print(f"{RED}{BOLD}{report.failed} de {total} verificações falharam{OFF}")
        return 1
    print(f"{GREEN}{BOLD}{passed}/{total} verificações passaram{OFF}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-ai",
        action="store_true",
        help="também exercita a proposta pela IA (consome OPENAI_API_KEY)",
    )
    args = parser.parse_args()
    # The report is the output. With DEBUG=true the engine is built with
    # echo on, which logs every statement — turn it off for this run.
    engine.echo = False
    sys.exit(asyncio.run(run(args.with_ai)))


if __name__ == "__main__":
    main()
