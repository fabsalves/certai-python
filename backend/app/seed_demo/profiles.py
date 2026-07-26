"""Deterministic per-profile assessment matrices for the demo cohort."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

# Lesson indices 0..5 match track order (Fundamentos 0-2, Prática 3-5).
LESSON_KEYS = (
    "leitura_critica",
    "estrutura_parecer",
    "primeiro_rascunho",
    "revisao_pares",
    "argumentacao",
    "entrega_final",
)

MODULE_KEYS = ("fundamentos", "pratica")

# Pending assessment is always on lesson 2 (Primeiro rascunho) for the 3 extras.
PENDING_LESSON_INDEX = 2

LevelKey = str | None  # "high"|"medium"|"low"|"very_low"|None


@dataclass(frozen=True)
class StudentPlan:
    """Resolved plan for one demo student."""

    profile: str
    # Per lesson 0..5: concluded?
    concluded: tuple[bool, ...]
    # Per lesson: level string, None (null evidence), or SKIP (not assessed / N/A).
    lesson_levels: tuple[LevelKey | object, ...]
    skip_assessment: tuple[bool, ...]  # True → concluded but no assessment row
    # Level string, None (null-evidence assessment), or SKIP (no row).
    module_levels: tuple[LevelKey | object, ...]
    track_level: LevelKey | object
    # Micro-score density hint: "full" | "sparse" | "none"
    micro_mode: str


class _Skip:
    """Sentinel: do not create assessment for this scope."""

    def __repr__(self) -> str:
        return "SKIP"


SKIP = _Skip()


def plan_for(profile: str, student_index: int, rng: Random) -> StudentPlan:
    """Build a coherent plan. student_index is the index within the profile group."""
    i = student_index

    if profile == "destaque":
        # Mostly high; at most one medium.
        base: list[LevelKey] = ["high", "high", "high", "high", "high", "high"]
        if i % 3 == 0:
            base[4] = "medium"
        elif i % 3 == 1:
            base[1] = "medium"
        return StudentPlan(
            profile=profile,
            concluded=(True,) * 6,
            lesson_levels=tuple(base),
            skip_assessment=(False,) * 6,
            module_levels=("high", "high"),
            track_level="high",
            micro_mode="full",
        )

    if profile == "consistente":
        patterns = [
            ["medium", "high", "medium", "high", "medium", "high"],
            ["high", "medium", "high", "medium", "high", "medium"],
            ["medium", "medium", "high", "medium", "high", "medium"],
            ["high", "high", "medium", "medium", "high", "medium"],
        ]
        levels = patterns[i % len(patterns)]
        track = "high" if levels.count("high") >= 4 else "medium"
        mod1 = "high" if levels[:3].count("high") >= 2 else "medium"
        mod2 = "high" if levels[3:].count("high") >= 2 else "medium"
        return StudentPlan(
            profile=profile,
            concluded=(True,) * 6,
            lesson_levels=tuple(levels),
            skip_assessment=(False,) * 6,
            module_levels=(mod1, mod2),
            track_level=track,
            micro_mode="full",
        )

    if profile == "irregular":
        patterns = [
            ["high", "low", "high", None, "medium", "low"],
            ["medium", "high", None, "low", "high", "medium"],
            ["low", "high", "medium", "high", None, "low"],
            ["high", None, "low", "medium", "low", "high"],
            ["medium", "low", "high", None, "high", "medium"],
        ]
        levels = list(patterns[i % len(patterns)])
        # Second null for some students.
        if i % 4 == 0 and levels.count(None) < 2:
            levels[5 if levels[5] is not None else 0] = None
        # Module: medium with rich gaps story; never high.
        return StudentPlan(
            profile=profile,
            concluded=(True,) * 6,
            lesson_levels=tuple(levels),
            skip_assessment=(False,) * 6,
            module_levels=("medium", "medium"),
            track_level="medium",
            micro_mode="full",
        )

    if profile == "dificuldade":
        patterns = [
            ["low", "very_low", "low", "very_low", "low", "very_low"],
            ["very_low", "low", "very_low", "low", "very_low", "low"],
            ["low", "low", "very_low", "low", "very_low", "low"],
            ["very_low", "very_low", "low", "very_low", "low", "very_low"],
        ]
        levels = patterns[i % len(patterns)]
        track = "very_low" if levels.count("very_low") >= 4 else "low"
        return StudentPlan(
            profile=profile,
            concluded=(True,) * 6,
            lesson_levels=tuple(levels),
            skip_assessment=(False,) * 6,
            module_levels=("low", "low" if track == "low" else "very_low"),
            track_level=track,
            micro_mode="full",
        )

    if profile == "pouco_engajado":
        # Majority null; maybe one weak level so the UI isn't all identical.
        levels: list[LevelKey] = [None, None, None, None, None, None]
        weak_slot = i % 6
        levels[weak_slot] = "low" if i % 2 == 0 else "very_low"
        return StudentPlan(
            profile=profile,
            concluded=(True,) * 6,
            lesson_levels=tuple(levels),
            skip_assessment=(False,) * 6,
            module_levels=(None, None),
            track_level=None,
            micro_mode="sparse",
        )

    if profile == "atrasado":
        # Student 0: misses last 2 lessons; student 1: misses last 1.
        miss = 2 if i % 2 == 0 else 1
        concluded = tuple(True if k < 6 - miss else False for k in range(6))
        # Strong start, then unfinished: no module/track.
        early = ["medium", "high", "medium", "high", "medium", "high"]
        levels: list[LevelKey | object] = []
        skip = []
        for k in range(6):
            if concluded[k]:
                levels.append(early[k])
                skip.append(False)
            else:
                levels.append(SKIP)
                skip.append(False)
        return StudentPlan(
            profile=profile,
            concluded=concluded,
            lesson_levels=tuple(levels),
            skip_assessment=tuple(skip),
            module_levels=(SKIP, SKIP),
            track_level=SKIP,
            micro_mode="full",
        )

    if profile == "pendente_avaliacao":
        # All concluded; consistent-ish levels; one lesson without assessment row.
        levels_list: list[LevelKey] = ["medium", "high", "medium", "medium", "high", "medium"]
        skip = [False] * 6
        skip[PENDING_LESSON_INDEX] = True
        return StudentPlan(
            profile=profile,
            concluded=(True,) * 6,
            lesson_levels=tuple(levels_list),
            skip_assessment=tuple(skip),
            module_levels=(SKIP, SKIP),
            track_level=SKIP,
            micro_mode="full",
        )

    raise ValueError(f"Unknown profile: {profile}")


def build_plans(students: list, rng: Random) -> dict[str, StudentPlan]:
    """Map email → plan. Indices restart per profile for stable variation."""
    counters: dict[str, int] = {}
    plans: dict[str, StudentPlan] = {}
    for student in students:
        idx = counters.get(student.profile, 0)
        counters[student.profile] = idx + 1
        plans[student.email] = plan_for(student.profile, idx, rng)
    return plans
