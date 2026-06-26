"""Scoped context assembly.

Principle: the "don't teach the future" restriction is structural, not a rule given
to the AI. The ContextBuilder hands the AI:

  - the track MAP (sequence, titles, where each thing lives) -> always, so the AI
    can orient ("you'll see this in Lesson 6");
  - the lesson CONTENT -> only up to where the cohort has reached (CohortProgress).

A future lesson has no content in the bundle. The AI cannot teach it because it
does not exist in the context -- with no textual rule.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment import CohortLessonNote
from app.models.track import Lesson, Module, Track
from app.models.cohort import Cohort, CohortProgress


@dataclass
class ContextBundle:
    """What the AI receives. Assembled, never parsed by regex/heuristics."""

    scope: str
    track_map: list[dict] = field(default_factory=list)        # always present
    unlocked_content: list[dict] = field(default_factory=list)  # only what the cohort saw
    cohort_notes: list[dict] = field(default_factory=list)
    current_position: dict | None = None

    def to_system_blocks(self) -> str:
        import json

        return (
            "## Track map (full sequence, titles only)\n"
            f"{json.dumps(self.track_map, ensure_ascii=False, indent=2)}\n\n"
            "## Unlocked content (lessons the cohort has studied)\n"
            f"{json.dumps(self.unlocked_content, ensure_ascii=False, indent=2)}\n\n"
            "## Notes for this cohort\n"
            f"{json.dumps(self.cohort_notes, ensure_ascii=False, indent=2)}\n\n"
            "## Student current position\n"
            f"{json.dumps(self.current_position, ensure_ascii=False, indent=2)}\n"
        )


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

    async def _unlocked_lessons(self, cohort_id: uuid.UUID) -> set[uuid.UUID]:
        stmt = select(CohortProgress.lesson_id).where(CohortProgress.cohort_id == cohort_id)
        return set((await self.db.execute(stmt)).scalars().all())

    async def build_lesson(
        self, cohort_id: uuid.UUID, lesson_id: uuid.UUID
    ) -> ContextBundle:
        """Context scoped to a specific lesson (student conversation)."""
        track = await self._track_of_cohort(cohort_id)
        unlocked = await self._unlocked_lessons(cohort_id)

        track_map: list[dict] = []
        content: list[dict] = []
        position = None
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
                if lesson.id in unlocked:
                    content.append({"lesson": lesson.title, "content": lesson.content})
                if lesson.id == lesson_id:
                    position = {"module": module.title, "lesson": lesson.title}

        notes = await self._notes(cohort_id, list(unlocked))
        return ContextBundle(
            scope="lesson",
            track_map=track_map,
            unlocked_content=content,
            cohort_notes=notes,
            current_position=position,
        )

    async def build_module(self, cohort_id: uuid.UUID, module_anchor_id: uuid.UUID) -> ContextBundle:
        """Scope widened to the module. Used when the AI escalates scope."""
        bundle = await self.build_lesson(cohort_id, module_anchor_id)  # reuses the map
        bundle.scope = "module"
        return bundle

    async def build_track(self, cohort_id: uuid.UUID) -> ContextBundle:
        """Widest scope: the whole track (limited to unlocked content)."""
        track = await self._track_of_cohort(cohort_id)
        unlocked = await self._unlocked_lessons(cohort_id)
        track_map = [
            {"module": m.title, "lesson": l.title, "unlocked": l.id in unlocked}
            for m in track.modules
            if m.is_active
            for l in m.lessons
            if l.is_active
        ]
        content = [
            {"lesson": l.title, "content": l.content}
            for m in track.modules
            if m.is_active
            for l in m.lessons
            if l.is_active and l.id in unlocked
        ]
        return ContextBundle(scope="track", track_map=track_map, unlocked_content=content)

    async def _notes(self, cohort_id: uuid.UUID, lesson_ids: list[uuid.UUID]) -> list[dict]:
        if not lesson_ids:
            return []
        stmt = select(CohortLessonNote).where(
            CohortLessonNote.cohort_id == cohort_id,
            CohortLessonNote.lesson_id.in_(lesson_ids),
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [{"summary": r.summary, "unclear_points": r.unclear_points} for r in rows]
