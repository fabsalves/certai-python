"""Planned vs. taught -- what a teaching session actually covered.

A session (one `CohortLessonNote`) keeps its anchor lesson and declares here the
real shape of what was taught: the anchor itself, the tail of an earlier lesson,
content of a later one, or all three. That makes the three real-world scenarios
recordable without touching the lesson sequence:

  - incomplete -> anchor `partial`, with what is missing in `pending`;
  - ahead      -> an extra segment on a later lesson;
  - composed   -> a `carryover` segment resolving the previous lesson's pendency.

The AI derives the segmentation from the professor's own report; the professor
confirms it. The code never infers coverage from words -- it only computes each
segment's `kind` from the lesson's position relative to the anchor, which is
arithmetic on the track sequence, not interpretation.

Coverage is append-only: the standing coverage of a lesson for a class is its
most recent row. A later session that covers a pending tail writes a new row with
an empty `pending`, so pendency resolves with no UPDATE and no parallel state.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_openai
from app.core.config import settings
from app.models.assessment import (
    CohortLessonNote,
    CoverageExtent,
    CoverageKind,
    LessonCoverage,
)
from app.models.cohort import Cohort, CohortModuleProfessor
from app.models.track import Lesson
from app.models.user import User
from app.schemas import (
    COVERAGE_TEXT_MAX,
    CoverageCandidateOut,
    CoverageNoticeOut,
    CoverageProposalOut,
    CoverageSegmentIn,
    CoverageSegmentOut,
)
from app.services.track_structure import ordered_active_lessons
from app.services.usage import UsageScope, record_chat_usage

logger = logging.getLogger(__name__)

# How far around the anchor a session may reach: the previous lesson (to close a
# pendency) and the next two (to absorb content taught ahead). Wider than this is
# not a deviation -- it is a different plan, and belongs to the designer.
LESSONS_BEFORE_ANCHOR = 1
LESSONS_AFTER_ANCHOR = 2

# The report is professor-authored free text of unbounded length. Cap what reaches
# the model so a pathological transcript cannot blow up the request.
TRANSCRIPT_MAX_CHARS = 12000

PROPOSAL_SYSTEM_PROMPT = (
    "Você recebe o relato de um professor sobre a aula que acabou de dar, mais o "
    "conteúdo planejado de algumas aulas vizinhas na trilha e o que cada uma "
    "ainda deve (pendência). Sua tarefa é dizer o que foi REALMENTE ministrado "
    "nesta sessão, aula por aula.\n\n"
    "Não presuma que a aula seguiu o plano. A aula real pode ter ficado "
    "incompleta, ter avançado no conteúdo da aula seguinte, ou ter começado "
    "fechando o que faltou da anterior. Derive isso do relato.\n\n"
    "Regras:\n"
    "- Só declare cobertura que o relato sustenta. Não invente.\n"
    "- A aula atual (marcada como ATUAL) sempre aparece, mesmo que parcial.\n"
    "- Uma aula vizinha só aparece se o relato indicar que ela foi tocada.\n"
    '- "extent": "full" quando o conteúdo daquela aula foi coberto por completo; '
    '"partial" quando só uma parte foi.\n'
    '- "covered": o que foi efetivamente ministrado daquela aula, em uma ou duas '
    "frases curtas, com suas palavras. NÃO copie o conteúdo planejado — "
    "descreva-o. O conteúdo planejado está aí para você identificar o que foi "
    "coberto, não para ser reproduzido.\n"
    '- "pending": o que daquela aula ainda falta, também em uma ou duas frases '
    'curtas. String vazia quando extent for "full".\n'
    "- Se a aula tinha pendência anterior e o relato indica que ela foi fechada "
    'agora, use extent "full" e pending vazio.\n\n'
    "Seja descritivo e neutro — nunca avaliativo sobre o professor.\n\n"
    "Pode haver uma seção de aulas de OUTRO PROFESSOR. Elas não podem entrar em "
    '"segments". Se o relato indicar que o professor avançou no conteúdo de uma '
    'delas, liste em "fora_do_alcance" com o que foi dado, para que ele saiba que '
    "não foi registrado. Se o relato não indicar nada disso, devolva uma lista "
    "vazia.\n\n"
    'Responda SOMENTE com um JSON: {"segments": [{"lesson_id": "...", '
    '"extent": "full"|"partial", "covered": "...", "pending": "..."}], '
    '"fora_do_alcance": [{"lesson_id": "...", "covered": "..."}]}'
)


def _clip(value: object) -> str:
    """LLM and professor text, bounded before it becomes a column or a prompt."""
    if not isinstance(value, str):
        return ""
    return value.strip()[:COVERAGE_TEXT_MAX]


async def recordable_module_owners(
    db: AsyncSession, cohort_id: uuid.UUID, module_class: CohortModuleProfessor
) -> dict[uuid.UUID, uuid.UUID]:
    """module_id -> the class that owns it, for every module this class may report on.

    Always its own module. Plus any other module of the cohort whose class is a
    single class taught by **the same professor**, and only when the anchor's own
    module is also a single class -- because then the audience is the whole cohort
    on both sides and the teacher is the same person, so a segment there is
    unambiguous.

    That condition is what makes teaching ahead across a module boundary
    recordable: it is an ordinary deviation when the same professor carries on
    into their next module, and it stops being one the moment a second professor
    or a split roster is involved. Then the audiences differ, the other professor
    will teach that lesson themselves, and nobody can say on their behalf what
    their class received -- see `unrecordable_neighbours`.

    A segment always lands under the class that owns the lesson, never under the
    session's anchor class: the owner is who will later close it and whose
    students read it in their context.
    """
    classes = (
        await db.scalars(
            select(CohortModuleProfessor).where(
                CohortModuleProfessor.cohort_id == cohort_id
            )
        )
    ).all()

    by_module: dict[uuid.UUID, list[CohortModuleProfessor]] = {}
    for item in classes:
        by_module.setdefault(item.module_id, []).append(item)

    owners = {module_class.module_id: module_class.id}
    if len(by_module.get(module_class.module_id, [])) > 1:
        # The anchor class is one of several in its module, so it teaches a
        # subset of the cohort. Nothing outside its own module is unambiguous.
        return owners

    for module_id, items in by_module.items():
        if module_id == module_class.module_id or len(items) != 1:
            continue
        if items[0].professor_id == module_class.professor_id:
            owners[module_id] = items[0].id
    return owners


async def unrecordable_neighbours(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    anchor_lesson_id: uuid.UUID,
    *,
    module_professor_id: uuid.UUID,
) -> list[tuple[Lesson, str]]:
    """Lessons right after the anchor that this class cannot report on.

    A professor really does finish their last lesson and carry on into the next
    module. When that module is someone else's, the content was taught but cannot
    be recorded here -- and the professor has to be told, instead of the segment
    being dropped in silence.
    """
    cohort = await db.get(Cohort, cohort_id)
    module_class = await db.get(CohortModuleProfessor, module_professor_id)
    if cohort is None or module_class is None:
        return []

    owners = await recordable_module_owners(db, cohort_id, module_class)
    ordered = await ordered_active_lessons(db, cohort.track_id)
    lesson_ids = [lesson.id for lesson in ordered]
    try:
        index = lesson_ids.index(anchor_lesson_id)
    except ValueError:
        return []

    out: list[tuple[Lesson, str]] = []
    for lesson in ordered[index + 1 : index + 1 + LESSONS_AFTER_ANCHOR]:
        if lesson.module_id in owners:
            continue
        names = (
            await db.scalars(
                select(User.name)
                .join(
                    CohortModuleProfessor,
                    CohortModuleProfessor.professor_id == User.id,
                )
                .where(
                    CohortModuleProfessor.cohort_id == cohort_id,
                    CohortModuleProfessor.module_id == lesson.module_id,
                )
                .order_by(User.name)
            )
        ).all()
        out.append((lesson, ", ".join(names)))
    return out


async def owning_class_ids(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    module_class: CohortModuleProfessor,
    lessons: list[Lesson],
) -> dict[uuid.UUID, uuid.UUID]:
    """lesson_id -> the class a coverage row for it must belong to."""
    owners = await recordable_module_owners(db, cohort_id, module_class)
    return {
        lesson.id: owners[lesson.module_id]
        for lesson in lessons
        if lesson.module_id in owners
    }


async def candidate_window(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    anchor_lesson_id: uuid.UUID,
    *,
    module_professor_id: uuid.UUID,
) -> list[Lesson]:
    """The lessons a session may legitimately touch, in teaching order.

    The anchor's neighbourhood, plus every earlier lesson that still owes this
    class something: a pendency does not expire when the class moves on, so it
    stays closable however many lessons later the professor gets back to it.

    Bounded to the modules this class may report on (see
    `recordable_module_owners`), which is its own plus any other taught by the
    same professor to the whole cohort.

    Reads the single track sequence everything else reads
    (`ordered_active_lessons`), so the window can never disagree with progression,
    and the result keeps that order -- which is what makes `kind_for` valid.
    """
    cohort = await db.get(Cohort, cohort_id)
    module_class = await db.get(CohortModuleProfessor, module_professor_id)
    if cohort is None or module_class is None:
        return []
    owners = await recordable_module_owners(db, cohort_id, module_class)
    ordered = [
        lesson
        for lesson in await ordered_active_lessons(db, cohort.track_id)
        if lesson.module_id in owners
    ]
    lesson_ids = [lesson.id for lesson in ordered]
    try:
        index = lesson_ids.index(anchor_lesson_id)
    except ValueError:
        return []

    chosen = set(
        range(
            max(0, index - LESSONS_BEFORE_ANCHOR),
            min(len(ordered), index + LESSONS_AFTER_ANCHOR + 1),
        )
    )
    if index > 0:
        # Per owning class: with the window spanning two modules, an earlier
        # lesson's pendency is recorded under the class that owns it, not under
        # the anchor's. Querying only the anchor's class would lose a pendency
        # left behind in the previous module -- and a pendency does not expire.
        earlier_by_owner: dict[uuid.UUID, list[uuid.UUID]] = {}
        for lesson in ordered[:index]:
            earlier_by_owner.setdefault(owners[lesson.module_id], []).append(lesson.id)
        for owner_id, ids in earlier_by_owner.items():
            pendings = await current_pendings(
                db,
                cohort_id=cohort_id,
                module_professor_id=owner_id,
                lesson_ids=ids,
            )
            chosen |= {lesson_ids.index(lesson_id) for lesson_id in pendings}

    return [ordered[position] for position in sorted(chosen)]


def kind_for(anchor_position: int, lesson_position: int) -> CoverageKind:
    """Where a segment sits relative to the anchor. Position arithmetic, not
    interpretation -- so a model can never mislabel a segment's origin."""
    if lesson_position < anchor_position:
        return CoverageKind.CARRYOVER
    if lesson_position > anchor_position:
        return CoverageKind.ADVANCE
    return CoverageKind.PLANNED


async def standing_coverage(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    module_professor_id: uuid.UUID,
    lesson_ids: list[uuid.UUID],
) -> dict[uuid.UUID, LessonCoverage]:
    """Most recent coverage row per lesson for one teaching class."""
    if not lesson_ids:
        return {}
    rows = (
        await db.scalars(
            select(LessonCoverage)
            .where(
                LessonCoverage.cohort_id == cohort_id,
                LessonCoverage.module_professor_id == module_professor_id,
                LessonCoverage.lesson_id.in_(lesson_ids),
            )
            .order_by(LessonCoverage.created_at.desc())
        )
    ).all()
    latest: dict[uuid.UUID, LessonCoverage] = {}
    for row in rows:
        latest.setdefault(row.lesson_id, row)
    return latest


async def current_pendings(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    module_professor_id: uuid.UUID,
    lesson_ids: list[uuid.UUID],
) -> dict[uuid.UUID, str]:
    """What each lesson still owes this class. Absent key = owes nothing."""
    latest = await standing_coverage(
        db,
        cohort_id=cohort_id,
        module_professor_id=module_professor_id,
        lesson_ids=lesson_ids,
    )
    return {
        lesson_id: row.pending.strip()
        for lesson_id, row in latest.items()
        if row.pending.strip()
    }


async def standing_coverage_for_cohort(
    db: AsyncSession, cohort_id: uuid.UUID
) -> dict[tuple[uuid.UUID, uuid.UUID], dict[str, str]]:
    """Standing coverage of every (lesson, class) pair of a cohort, in one query.

    Feeds the professor-facing progress panel, where pendency is the delta the
    doc asks to keep visible as operational data. Keyed by (lesson_id,
    module_professor_id); a pair with no coverage is simply absent.
    """
    rows = (
        await db.scalars(
            select(LessonCoverage)
            .where(LessonCoverage.cohort_id == cohort_id)
            .order_by(LessonCoverage.created_at.desc())
        )
    ).all()
    latest: dict[tuple[uuid.UUID, uuid.UUID], dict[str, str]] = {}
    for row in rows:
        key = (row.lesson_id, row.module_professor_id)
        if key in latest:
            continue
        latest[key] = {
            "covered": row.covered,
            "pending": row.pending,
            "extent": row.extent.value,
        }
    return latest


async def session_scope(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    module_professor_id: uuid.UUID,
    anchor_lesson_id: uuid.UUID,
) -> list[dict]:
    """The real scope of the session anchored on this lesson.

    This is what the student actually received in that session -- the authority
    for both the conversation and the assessment. Returns [] for sessions closed
    before coverage existed, and callers fall back to the planned content, so the
    happy path is unchanged.
    """
    note = await db.scalar(
        select(CohortLessonNote)
        .where(
            CohortLessonNote.cohort_id == cohort_id,
            CohortLessonNote.lesson_id == anchor_lesson_id,
            CohortLessonNote.module_professor_id == module_professor_id,
        )
        .order_by(CohortLessonNote.created_at.desc())
        .limit(1)
    )
    if note is None:
        return []

    rows = (
        await db.execute(
            select(LessonCoverage, Lesson.title)
            .join(Lesson, LessonCoverage.lesson_id == Lesson.id)
            .where(LessonCoverage.note_id == note.id)
            .order_by(LessonCoverage.created_at)
        )
    ).all()

    scope: list[dict] = []
    for row, title in rows:
        if _is_bare_default(row):
            continue
        scope.append(
            {
                "lesson": title,
                "origin": row.kind.value,
                "extent": row.extent.value,
                "covered": row.covered,
                "pending": row.pending,
            }
        )
    return scope


def _says_nothing_new(segment: CoverageSegmentIn, anchor_lesson_id: uuid.UUID) -> bool:
    """True when a segment reports the plan being followed, and nothing else.

    Only meaningful for a lone segment: once a session touches a second lesson,
    the coverage is informative and every segment's description matters, the
    anchor's included.
    """
    return (
        segment.lesson_id == anchor_lesson_id
        and segment.kind == "planned"
        and segment.extent == "full"
        and not segment.pending.strip()
    )


def _is_bare_default(row: LessonCoverage) -> bool:
    """The happy path carries no information beyond "the plan was followed".

    Filtering it out keeps the context bundle and the evaluator prompt byte-identical
    to what they were before coverage existed, whenever the lesson did go as planned.
    """
    return (
        row.kind == CoverageKind.PLANNED
        and row.extent == CoverageExtent.FULL
        and not row.covered.strip()
        and not row.pending.strip()
    )


async def own_pendency(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    module_professor_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> str:
    """What this lesson's own session declared as not taught.

    Distinct from `current_pendings`: this survives a later session closing the
    tail, so a reader can tell "nothing was ever missing" from "it was missing
    and has since been delivered".
    """
    row = await db.scalar(
        select(LessonCoverage)
        .where(
            LessonCoverage.cohort_id == cohort_id,
            LessonCoverage.module_professor_id == module_professor_id,
            LessonCoverage.lesson_id == lesson_id,
            LessonCoverage.kind == CoverageKind.PLANNED,
        )
        .order_by(LessonCoverage.created_at.desc())
        .limit(1)
    )
    return row.pending.strip() if row is not None else ""


async def later_carryover(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    module_professor_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> dict | None:
    """A pendency of this lesson delivered later, in another session.

    The evidence for that content lives in the conversation of the session that
    delivered it -- which the lesson's own evaluator needs to know, so it reports
    the right gap instead of a false absence.
    """
    row = await db.execute(
        select(LessonCoverage, Lesson.title)
        .join(CohortLessonNote, LessonCoverage.note_id == CohortLessonNote.id)
        .join(Lesson, CohortLessonNote.lesson_id == Lesson.id)
        .where(
            LessonCoverage.cohort_id == cohort_id,
            LessonCoverage.module_professor_id == module_professor_id,
            LessonCoverage.lesson_id == lesson_id,
            LessonCoverage.kind == CoverageKind.CARRYOVER,
        )
        .order_by(LessonCoverage.created_at.desc())
        .limit(1)
    )
    found = row.first()
    if found is None:
        return None
    coverage, anchor_title = found
    return {"covered": coverage.covered, "delivered_in": anchor_title}


def default_segment(anchor_lesson_id: uuid.UUID) -> CoverageSegmentIn:
    """The happy path: the anchor lesson, fully covered, nothing pending.

    Used when no coverage is informed, so a client that does not know about
    coverage at all behaves exactly as before.
    """
    return CoverageSegmentIn(
        lesson_id=anchor_lesson_id,
        kind="planned",
        extent="full",
        covered="",
        pending="",
        source="ai",
    )


async def unhonoured_segments(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    anchor_lesson_id: uuid.UUID,
    *,
    module_professor_id: uuid.UUID,
    segments: list[CoverageSegmentIn],
) -> list[Lesson]:
    """Confirmed segments this class cannot record, so the professor is told.

    `persist_coverage` drops them either way -- that guard stays. The point here
    is the difference between the two places a segment can be dropped:

      - at proposal time it is a model slip, and staying quiet is right;
      - at persist time the professor confirmed it, so silence would lose what a
        human declared. That is the failure mode this package exists to remove.

    Normally empty: the UI only offers lessons from the window the proposal
    returned. It fills when the window shrank in between -- the module's
    professor was reassigned, say -- or when a request was crafted by hand.
    """
    if not segments:
        return []
    window = await candidate_window(
        db, cohort_id, anchor_lesson_id, module_professor_id=module_professor_id
    )
    allowed = {lesson.id for lesson in window}
    missing = [s.lesson_id for s in segments if s.lesson_id not in allowed]
    if not missing:
        return []
    return list(
        (await db.scalars(select(Lesson).where(Lesson.id.in_(missing)))).all()
    )


async def persist_coverage(
    db: AsyncSession,
    *,
    note: CohortLessonNote,
    segments: list[CoverageSegmentIn],
    allowed_positions: dict[uuid.UUID, int],
    anchor_position: int,
    owners: dict[uuid.UUID, uuid.UUID] | None = None,
) -> list[LessonCoverage]:
    """Write the confirmed coverage of a session.

    `allowed_positions` is the validated candidate window: a segment outside it
    is dropped rather than trusted, so neither a model nor a crafted request can
    write coverage against an arbitrary lesson.

    `owners` maps each candidate lesson to the class a row for it must belong to.
    That is the anchor's own class for its module, and the other module's class
    when the same professor carries on into it -- the owner is who will later
    close the lesson and whose students read it.
    """
    # A lone segment on the anchor, fully covered, owing nothing, says only "the
    # plan was followed". The proposal fills `covered` with a description so the
    # professor can see the AI understood the report, but persisting that text
    # would put a two-sentence paraphrase in the context bundle -- declared to the
    # engine as the authority, outranking the lesson's real material. So the happy
    # path is stored bare, and the bundle stays exactly as it was before coverage.
    if len(segments) == 1 and _says_nothing_new(segments[0], note.lesson_id):
        segments = [default_segment(note.lesson_id)]

    rows: list[LessonCoverage] = []
    seen: set[uuid.UUID] = set()
    for segment in segments:
        position = allowed_positions.get(segment.lesson_id)
        if position is None or segment.lesson_id in seen:
            continue
        seen.add(segment.lesson_id)
        rows.append(
            LessonCoverage(
                note_id=note.id,
                cohort_id=note.cohort_id,
                lesson_id=segment.lesson_id,
                module_professor_id=(owners or {}).get(
                    segment.lesson_id, note.module_professor_id
                ),
                kind=kind_for(anchor_position, position),
                extent=CoverageExtent(segment.extent),
                covered=segment.covered,
                pending=segment.pending,
                source=segment.source,
            )
        )

    if note.lesson_id not in seen:
        # The anchor is always part of its own session, whatever came in.
        rows.append(
            LessonCoverage(
                note_id=note.id,
                cohort_id=note.cohort_id,
                lesson_id=note.lesson_id,
                module_professor_id=note.module_professor_id,
                kind=CoverageKind.PLANNED,
                extent=CoverageExtent.FULL,
                covered="",
                pending="",
                source="ai",
            )
        )

    for row in rows:
        db.add(row)
    await db.flush()
    return rows


def _window_block(
    window: list[Lesson],
    *,
    anchor_lesson_id: uuid.UUID,
    anchor_position: int,
    pendings: dict[uuid.UUID, str],
) -> str:
    parts: list[str] = []
    for position, lesson in enumerate(window):
        if lesson.id == anchor_lesson_id:
            label = "ATUAL (a aula que o professor está encerrando)"
        elif position < anchor_position:
            label = "anterior na trilha"
        else:
            label = "posterior na trilha"
        pending = pendings.get(lesson.id, "")
        parts.append(
            f"### {lesson.title}\n"
            f"lesson_id: {lesson.id}\n"
            f"papel: {label}\n"
            f"pendência atual: {pending or '(nenhuma)'}\n"
            f"conteúdo planejado:\n{lesson.content.strip() or '(sem conteúdo cadastrado)'}"
        )
    return "\n\n".join(parts)


async def propose_coverage(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    module_professor_id: uuid.UUID,
    anchor_lesson_id: uuid.UUID,
    transcript: str,
) -> CoverageProposalOut:
    """Derive the session's real coverage from the professor's own report.

    Professor-facing: this is the one LLM call that sees the planned content of
    future lessons. It never touches the student's engine or context bundle -- the
    excess only reaches a student as a description of what was said in class, so
    the "don't teach the future" barrier stays structural.

    Never raises: a failure returns the anchor-only default with `from_ai=False`,
    and the professor can still close the lesson.
    """
    window = await candidate_window(
        db, cohort_id, anchor_lesson_id, module_professor_id=module_professor_id
    )
    titles = {lesson.id: lesson.title for lesson in window}
    positions = {lesson.id: index for index, lesson in enumerate(window)}
    anchor_position = positions.get(anchor_lesson_id)

    pendings = (
        await current_pendings(
            db,
            cohort_id=cohort_id,
            module_professor_id=module_professor_id,
            lesson_ids=list(positions),
        )
        if positions
        else {}
    )
    candidates = [
        CoverageCandidateOut(
            lesson_id=lesson.id,
            lesson_title=lesson.title,
            is_anchor=lesson.id == anchor_lesson_id,
            standing_pending=pendings.get(lesson.id, ""),
        )
        for lesson in window
    ]

    def _anchor_only(*, from_ai: bool) -> CoverageProposalOut:
        return CoverageProposalOut(
            anchor_lesson_id=anchor_lesson_id,
            segments=[
                CoverageSegmentOut(
                    **default_segment(anchor_lesson_id).model_dump(),
                    lesson_title=titles.get(anchor_lesson_id, ""),
                )
            ],
            candidates=candidates,
            from_ai=from_ai,
        )

    fallback = _anchor_only(from_ai=False)

    # No report to read, or a lesson outside the track sequence: nothing to derive.
    if not window or anchor_position is None or not transcript.strip():
        return fallback

    window_block = _window_block(
        window,
        anchor_lesson_id=anchor_lesson_id,
        anchor_position=anchor_position,
        pendings=pendings,
    )
    user_content = (
        f"## Relato do professor\n{transcript.strip()[:TRANSCRIPT_MAX_CHARS]}\n\n"
        f"## Aulas candidatas (em ordem na trilha)\n{window_block}"
    )
    # Read-only: the model may point at these to warn, never to record.
    blocked = await unrecordable_neighbours(
        db, cohort_id, anchor_lesson_id, module_professor_id=module_professor_id
    )
    if blocked:
        user_content += "\n\n## Aulas de OUTRO PROFESSOR (não registráveis)\n" + "\n\n".join(
            f"### {lesson.title}\nlesson_id: {lesson.id}\nprofessor: {name}\n"
            f"conteúdo planejado:\n{lesson.content.strip() or '(sem conteúdo cadastrado)'}"
            for lesson, name in blocked
        )

    try:
        client = get_openai()
        resp = await client.chat.completions.create(
            model=settings.ENGINE_MODEL,
            max_tokens=1500,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PROPOSAL_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        await record_chat_usage(
            db,
            scope=UsageScope(cohort_id=cohort_id, lesson_id=anchor_lesson_id),
            operation="coverage",
            response=resp,
        )
        payload = json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        logger.warning(
            "coverage proposal failed cohort=%s lesson=%s",
            cohort_id,
            anchor_lesson_id,
            exc_info=True,
        )
        return fallback

    raw = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return fallback

    segments: list[CoverageSegmentOut] = []
    seen: set[uuid.UUID] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            lesson_id = uuid.UUID(str(item.get("lesson_id", "")))
        except ValueError:
            continue
        # A lesson outside the window is a model slip, not a deviation to record.
        position = positions.get(lesson_id)
        if position is None or lesson_id in seen:
            continue
        seen.add(lesson_id)
        extent = "partial" if str(item.get("extent", "")).lower() == "partial" else "full"
        segments.append(
            CoverageSegmentOut(
                lesson_id=lesson_id,
                kind=kind_for(anchor_position, position).value,
                extent=extent,
                covered=_clip(item.get("covered")),
                pending=_clip(item.get("pending")),
                lesson_title=titles.get(lesson_id, ""),
            )
        )

    if anchor_lesson_id not in seen:
        segments.append(
            CoverageSegmentOut(
                **default_segment(anchor_lesson_id).model_dump(),
                lesson_title=titles.get(anchor_lesson_id, ""),
            )
        )

    blocked_by_id = {lesson.id: (lesson, name) for lesson, name in blocked}
    notices: list[CoverageNoticeOut] = []
    raw_blocked = payload.get("fora_do_alcance") if isinstance(payload, dict) else None
    for item in raw_blocked if isinstance(raw_blocked, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            lesson_id = uuid.UUID(str(item.get("lesson_id", "")))
        except ValueError:
            continue
        found = blocked_by_id.pop(lesson_id, None)
        if found is None:
            continue
        lesson, name = found
        notices.append(
            CoverageNoticeOut(
                lesson_title=lesson.title,
                professor_name=name,
                covered=_clip(item.get("covered")),
            )
        )

    segments.sort(key=lambda item: positions[item.lesson_id])
    return CoverageProposalOut(
        anchor_lesson_id=anchor_lesson_id,
        segments=segments,
        candidates=candidates,
        unrecordable=notices,
        from_ai=True,
    )


async def coverage_block_for_note(db: AsyncSession, note_id: uuid.UUID) -> str:
    """The session's coverage as pt-BR text, for the consolidation prompt.

    Ends with the neighbouring lessons this class cannot report on, named one by
    one. A general rule ("stay inside the coverage") does not hold: the report
    mentions the lesson the professor advanced into, and summarising the report is
    the model's primary job, so it writes it down. Naming the lesson turns the
    restriction into data -- the same reason the future never enters the student's
    bundle as a rule, only as an absence.
    """
    rows = (
        await db.execute(
            select(LessonCoverage, Lesson.title)
            .join(Lesson, LessonCoverage.lesson_id == Lesson.id)
            .where(LessonCoverage.note_id == note_id)
            .order_by(LessonCoverage.created_at)
        )
    ).all()
    if not rows:
        return ""

    origin_label = {
        CoverageKind.PLANNED: "aula do dia",
        CoverageKind.CARRYOVER: "conteúdo pendente da aula anterior, fechado nesta sessão",
        CoverageKind.ADVANCE: "conteúdo da aula seguinte, dado adiantado",
    }
    extent_label = {
        CoverageExtent.FULL: "coberta por completo",
        CoverageExtent.PARTIAL: "coberta parcialmente",
    }

    parts: list[str] = []
    for row, title in rows:
        block = (
            f"### {title} ({origin_label[row.kind]})\n"
            f"situação: {extent_label[row.extent]}\n"
            f"ministrado: {row.covered.strip() or '(sem detalhe)'}"
        )
        if row.pending.strip():
            block += f"\nnão ministrado: {row.pending.strip()}"
        parts.append(block)

    note = await db.get(CohortLessonNote, note_id)
    if note is not None:
        blocked = await unrecordable_neighbours(
            db,
            note.cohort_id,
            note.lesson_id,
            module_professor_id=note.module_professor_id,
        )
        if blocked:
            names = ", ".join(f'"{lesson.title}"' for lesson, _ in blocked)
            parts.append(
                "### Aulas que NÃO fazem parte desta sessão\n"
                f"{names}\n"
                "São de outro professor. Mesmo que o relato as mencione, não "
                "escreva nada sobre elas em nenhum dos três campos, nem de "
                "passagem: estes alunos não as receberam."
            )
    return "\n\n".join(parts)
