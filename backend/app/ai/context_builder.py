"""Scoped context assembly.

Principle: the "don't teach the future" restriction is structural, not a rule given
to the AI. The ContextBuilder hands the AI:

  - the track MAP (sequence, titles, where each thing lives) -> always, so the AI
    can orient ("you'll see this in Lesson 6");
  - the current lesson CONTENT -> full catalog + that module's description + full class note;
  - prior unlocked lessons -> note summary/unclear_points only (no catalog, no KB);
  - what the session ACTUALLY taught -> only when it diverged from the plan.

The last one separates planned from taught. A lesson may have been left incomplete,
absorbed the tail of the previous one, or run ahead into the next: the bundle says
which, so the AI works on what the student received instead of what was scheduled.
Content taught ahead enters as a description of what was said in class -- never as
the next lesson's catalog, so the barrier below still holds.

A future lesson has no content in the bundle. The AI cannot teach it because it
does not exist in the context -- with no textual rule.

The same principle scopes the bundle to the student's own class: when a module
is taught by two professors, only what that student's professor closed and
reported reaches them.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment import CohortLessonNote
from app.models.track import Lesson, Module, Track
from app.models.cohort import Cohort, CohortProgress
from app.services import coverage_service
from app.services.cohort import ModuleClassService
from app.services.ingestion import INGESTION_DONE


@dataclass
class ContextBundle:
    """What the AI receives. Assembled, never parsed by regex/heuristics."""

    scope: str
    track_map: list[dict] = field(default_factory=list)        # always present
    unlocked_content: list[dict] = field(default_factory=list)  # current module + lesson catalog
    cohort_notes: list[dict] = field(default_factory=list)
    current_position: dict | None = None
    track_guide: str = ""  # macro guide from the track material, available at any lesson
    # What the session that closed this lesson ACTUALLY taught, per lesson: the
    # anchor, plus a pending tail of the previous lesson or content taught ahead.
    # Empty whenever the lesson went as planned -- then the planned content is the
    # whole story and this block does not appear at all.
    taught_scope: list[dict] = field(default_factory=list)

    def to_system_blocks(self) -> str:
        import json

        blocks = (
            "## Track map (full sequence, titles only)\n"
            f"{json.dumps(self.track_map, ensure_ascii=False, indent=2)}\n\n"
        )
        if self.taught_scope:
            blocks += (
                "## What this session actually taught (authority for this lesson)\n"
                "Diverged from the plan. `covered` is what the student received; "
                "`pending` was NOT taught to them. `origin`: planned = this lesson, "
                "carryover = tail of the previous one closed in this session, "
                "advance = content of the next one taught ahead.\n"
                f"{json.dumps(self.taught_scope, ensure_ascii=False, indent=2)}\n\n"
            )
        blocks += (
            "## Current lesson content\n"
            f"{json.dumps(self.unlocked_content, ensure_ascii=False, indent=2)}\n\n"
            "## Notes for this cohort\n"
            f"{json.dumps(self.cohort_notes, ensure_ascii=False, indent=2)}\n\n"
            "## Student current position\n"
            f"{json.dumps(self.current_position, ensure_ascii=False, indent=2)}\n"
        )
        if self.track_guide.strip():
            blocks += (
                "\n## Track guide (macro reference from the track material)\n"
                f"{self.track_guide.strip()}\n"
            )
        return blocks


class ContextBuilder:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _track_of_cohort(self, cohort_id: uuid.UUID) -> Track:
        cohort = await self.db.get(Cohort, cohort_id)
        stmt = (
            select(Track)
            .where(Track.id == cohort.track_id)
            .options(selectinload(Track.modules).selectinload(Module.lessons))
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def _student_classes_by_module(
        self, cohort_id: uuid.UUID, student_id: uuid.UUID
    ) -> dict[uuid.UUID, uuid.UUID]:
        """The class this student belongs to, per module."""
        return await ModuleClassService.classes_by_module_for_student(
            self.db, cohort_id, student_id
        )

    async def _student_class_ids(
        self, cohort_id: uuid.UUID, student_id: uuid.UUID
    ) -> set[uuid.UUID]:
        """The classes this student belongs to, one per module. Everything the
        student may see is scoped to them."""
        resolved = await self._student_classes_by_module(cohort_id, student_id)
        return set(resolved.values())

    async def _unlocked_lessons(
        self, cohort_id: uuid.UUID, class_ids: set[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Only what the student's own professor already closed. Another class
        moving ahead never unlocks content here."""
        if not class_ids:
            return set()
        stmt = select(CohortProgress.lesson_id).where(
            CohortProgress.cohort_id == cohort_id,
            CohortProgress.module_professor_id.in_(class_ids),
        )
        return set((await self.db.execute(stmt)).scalars().all())

    async def build_lesson(
        self, cohort_id: uuid.UUID, lesson_id: uuid.UUID, *, student_id: uuid.UUID
    ) -> ContextBundle:
        """Context scoped to a specific lesson (student conversation)."""
        track = await self._track_of_cohort(cohort_id)
        classes_by_module = await self._student_classes_by_module(cohort_id, student_id)
        class_ids = set(classes_by_module.values())
        unlocked = await self._unlocked_lessons(cohort_id, class_ids)

        track_map: list[dict] = []
        content: list[dict] = []
        position = None
        anchor_module_id: uuid.UUID | None = None
        for module in track.modules:
            if not module.is_active:
                continue
            for lesson in module.lessons:
                if not lesson.is_active:
                    continue
                track_map.append(
                    {
                        "module": module.title,
                        "level": module.level.value,
                        "lesson": lesson.title,
                        "lesson_id": str(lesson.id),
                        "unlocked": lesson.id in unlocked,
                    }
                )
                # Full catalog only for the current lesson (when unlocked),
                # plus that module's description (raw, same role as lesson.content).
                if lesson.id == lesson_id and lesson.id in unlocked:
                    content.append(
                        {"module": module.title, "description": module.description}
                    )
                    content.append({"lesson": lesson.title, "content": lesson.content})
                if lesson.id == lesson_id:
                    anchor_module_id = module.id
                    position = {
                        "track": track.title,
                        "module": module.title,
                        "lesson": lesson.title,
                    }

        notes = await self._notes(
            cohort_id, list(unlocked), class_ids, current_lesson_id=lesson_id
        )
        # Only for an unlocked lesson: a locked one has no session to report on.
        # Scoped to this student's own class, like everything else here.
        anchor_class_id = (
            classes_by_module.get(anchor_module_id)
            if anchor_module_id is not None
            else None
        )
        taught_scope: list[dict] = []
        if anchor_class_id is not None and lesson_id in unlocked:
            taught_scope = await coverage_service.session_scope(
                self.db,
                cohort_id=cohort_id,
                module_professor_id=anchor_class_id,
                anchor_lesson_id=lesson_id,
            )
        return ContextBundle(
            scope="lesson",
            track_map=track_map,
            unlocked_content=content,
            cohort_notes=notes,
            current_position=position,
            track_guide=(
                track.material_guide
                if track.material_ingestion_status == INGESTION_DONE
                else ""
            ),
            taught_scope=taught_scope,
        )

    async def build_module(
        self,
        cohort_id: uuid.UUID,
        module_anchor_id: uuid.UUID,
        *,
        student_id: uuid.UUID,
    ) -> ContextBundle:
        """Scope widened to the module. Used when the AI escalates scope."""
        bundle = await self.build_lesson(
            cohort_id, module_anchor_id, student_id=student_id
        )  # reuses the map
        bundle.scope = "module"
        return bundle

    async def build_track(
        self, cohort_id: uuid.UUID, *, student_id: uuid.UUID
    ) -> ContextBundle:
        """Widest scope: the whole track (limited to unlocked content)."""
        track = await self._track_of_cohort(cohort_id)
        class_ids = await self._student_class_ids(cohort_id, student_id)
        unlocked = await self._unlocked_lessons(cohort_id, class_ids)
        track_map = [
            {"module": m.title, "lesson": l.title, "unlocked": l.id in unlocked}
            for m in track.modules
            if m.is_active
            for l in m.lessons
            if l.is_active
        ]
        content: list[dict] = []
        for module in track.modules:
            if not module.is_active:
                continue
            unlocked_lessons = [
                lesson
                for lesson in module.lessons
                if lesson.is_active and lesson.id in unlocked
            ]
            if not unlocked_lessons:
                continue
            content.append(
                {"module": module.title, "description": module.description}
            )
            content.extend(
                {"lesson": lesson.title, "content": lesson.content}
                for lesson in unlocked_lessons
            )
        return ContextBundle(
            scope="track",
            track_map=track_map,
            unlocked_content=content,
            track_guide=(
                track.material_guide
                if track.material_ingestion_status == INGESTION_DONE
                else ""
            ),
        )

    async def _notes(
        self,
        cohort_id: uuid.UUID,
        lesson_ids: list[uuid.UUID],
        class_ids: set[uuid.UUID],
        *,
        current_lesson_id: uuid.UUID | None = None,
    ) -> list[dict]:
        """Reports written by this student's own professors. When a module has
        two professors, the other one's report never reaches this student."""
        if not lesson_ids or not class_ids:
            return []
        stmt = (
            select(CohortLessonNote, Lesson.title)
            .join(Lesson, CohortLessonNote.lesson_id == Lesson.id)
            .where(
                CohortLessonNote.cohort_id == cohort_id,
                CohortLessonNote.lesson_id.in_(lesson_ids),
                CohortLessonNote.module_professor_id.in_(class_ids),
                CohortLessonNote.ingestion_status == INGESTION_DONE,
            )
        )
        rows = (await self.db.execute(stmt)).all()
        result: list[dict] = []
        for note, title in rows:
            entry: dict = {
                "lesson": title,
                "summary": note.summary,
                "unclear_points": note.unclear_points,
            }
            # Full note (incl. knowledge_base) only for the current lesson.
            if current_lesson_id is None or note.lesson_id == current_lesson_id:
                entry["knowledge_base"] = note.attachment_knowledge_base
            result.append(entry)
        return result
