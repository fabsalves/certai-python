"""Read-only diagnostic: inspect Lira context size for a cohort/student/lesson.

Usage (from backend/ with venv active):

  python scripts/inspect_context.py \\
    --cohort-id UUID --student-id UUID --lesson-id UUID [--full]

Does not mutate DB, call OpenAI, or change production builders.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.context_builder import ContextBuilder, ContextBundle
from app.ai.engine import SYSTEM_BASE
from app.ai.persona import LIRA_TONE
from app.core.database import SessionLocal, engine
from app.models.cohort import Cohort
from app.models.track import Lesson, Module, Track
from app.models.user import User
from app.services.conversation_service import lesson_conversation_history
from app.services.realtime.instructions_builder import (
    CLOSURE_BLOCK,
    INSTRUCTIONS_CHAR_LIMIT,
    LESSON_CLOSURE_BLOCK,
    LESSON_CLOSURE_CALL_END,
    OPENING_BLOCK,
    PERSUASION_BLOCK,
    RESUMPTION_BLOCK,
    VOICE_CONVERSATION_ORDER_BLOCK,
    VOICE_MODE_BLOCK,
    format_history,
)

# Keep diagnostic stdout clean (DEBUG echo is noisy).
engine.echo = False
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

SNIPPET_CHARS = 500


def _first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else full_name


def _tokens(chars: int) -> int:
    return chars // 4


def _limit_delta(chars: int) -> str:
    delta = INSTRUCTIONS_CHAR_LIMIT - chars
    if delta >= 0:
        return f"sobra {delta:,} chars"
    return f"excede {abs(delta):,} chars"


def _print_text(label: str, text: str, *, full: bool) -> None:
    n = len(text)
    print(f"\n--- {label} ({n:,} chars, ~{_tokens(n):,} tokens) ---")
    if full or n <= SNIPPET_CHARS:
        print(text if text else "(empty)")
    else:
        print(text[:SNIPPET_CHARS])
        print(f"... (truncated, {n:,} chars total)")


def _serialize_blocks(bundle: ContextBundle) -> dict[str, str]:
    """Rebuild each section with the same format as ContextBundle.to_system_blocks()."""
    blocks = {
        "track_map": (
            "## Track map (full sequence, titles only)\n"
            f"{json.dumps(bundle.track_map, ensure_ascii=False, indent=2)}\n\n"
        ),
        "unlocked_content": (
            "## Current lesson content\n"
            f"{json.dumps(bundle.unlocked_content, ensure_ascii=False, indent=2)}\n\n"
        ),
        "cohort_notes": (
            "## Notes for this cohort\n"
            f"{json.dumps(bundle.cohort_notes, ensure_ascii=False, indent=2)}\n\n"
        ),
        "current_position": (
            "## Student current position\n"
            f"{json.dumps(bundle.current_position, ensure_ascii=False, indent=2)}\n"
        ),
        "track_guide": "",
    }
    if bundle.track_guide.strip():
        blocks["track_guide"] = (
            "\n## Track guide (macro reference from the track material)\n"
            f"{bundle.track_guide.strip()}\n"
        )
    return blocks


def _assemble_voice_instructions(
    *,
    system_blocks: str,
    history: list[dict],
    student_first_name: str,
) -> tuple[str, dict[str, int]]:
    """Same formula as RealtimeInstructionsBuilder._assemble, without truncation/LLM."""
    base_prefix = (
        f"{SYSTEM_BASE}\n\n{VOICE_CONVERSATION_ORDER_BLOCK}\n\n{LIRA_TONE}\n\n"
        f"{system_blocks}\n\n"
        f"{VOICE_MODE_BLOCK}\n\n{PERSUASION_BLOCK}\n\n{CLOSURE_BLOCK}\n\n"
        f"{LESSON_CLOSURE_BLOCK}\n{LESSON_CLOSURE_CALL_END}\n\n"
    )
    student_block = f"## Aluno\nPrimeiro nome: {student_first_name}\n\n"
    hist_block = format_history(history)
    history_section = f"## Histórico da conversa desta aula\n{hist_block}\n\n"
    opening_tail = f"{OPENING_BLOCK}\n\n{RESUMPTION_BLOCK}"

    fixed_before_blocks = (
        f"{SYSTEM_BASE}\n\n{VOICE_CONVERSATION_ORDER_BLOCK}\n\n{LIRA_TONE}\n\n"
    )
    fixed_after_blocks = (
        f"\n\n{VOICE_MODE_BLOCK}\n\n{PERSUASION_BLOCK}\n\n{CLOSURE_BLOCK}\n\n"
        f"{LESSON_CLOSURE_BLOCK}\n{LESSON_CLOSURE_CALL_END}\n\n"
    )

    full = (
        f"{base_prefix}"
        f"{student_block}"
        f"{history_section}"
        f"{opening_tail}"
    )
    breakdown = {
        "fixed_prefix_persona_order_tone": len(fixed_before_blocks),
        "system_blocks": len(system_blocks),
        "fixed_voice_closure_blocks": len(fixed_after_blocks),
        "aluno": len(student_block),
        "historico": len(history_section),
        "abertura_retomada": len(opening_tail),
    }
    return full, breakdown


def _slim_note(note: dict) -> dict:
    """Prior-lesson note shape: summary + unclear_points only (no knowledge_base)."""
    return {
        "lesson": note.get("lesson") or "",
        "summary": note.get("summary") or "",
        "unclear_points": note.get("unclear_points") or "",
    }


def _notes_block_len(notes: list[dict]) -> int:
    return len(
        "## Notes for this cohort\n"
        f"{json.dumps(notes, ensure_ascii=False, indent=2)}\n\n"
    )


def _project_cohort_notes_all_unlocked(
    *,
    cohort_notes: list[dict],
    current_lesson_title: str | None,
    n_total: int,
) -> tuple[int, str]:
    """Project notes block when every track lesson is unlocked.

    Current lesson keeps the full note; the other (n_total - 1) entries are slim
    (summary + unclear_points), sized by re-serializing real fields without KB.
    """
    if n_total <= 0:
        return _notes_block_len([]), "sem aulas na trilha"

    current_full = next(
        (n for n in cohort_notes if n.get("lesson") == current_lesson_title),
        None,
    )
    if current_full is None:
        current_full = next(
            (n for n in cohort_notes if "knowledge_base" in n),
            None,
        )

    slim_templates = [_slim_note(n) for n in cohort_notes]
    if current_full is None and not slim_templates:
        return _notes_block_len([]), "sem notas para estimar"

    if current_full is None:
        # No current full note — estimate all slots as slim.
        projected = [
            slim_templates[i % len(slim_templates)] for i in range(n_total)
        ]
        return (
            _notes_block_len(projected),
            f"{n_total} slim (sem nota completa da aula atual)",
        )

    n_prior = n_total - 1
    others = [
        _slim_note(n)
        for n in cohort_notes
        if n.get("lesson") != current_full.get("lesson")
    ]
    templates = others or slim_templates or [_slim_note(current_full)]
    priors: list[dict] = list(others)
    while len(priors) < n_prior:
        priors.append(templates[len(priors) % len(templates)])
    priors = priors[:n_prior]

    projected = [current_full] + priors
    return (
        _notes_block_len(projected),
        f"1 completa (aula atual) + {n_prior} slim (sem knowledge_base)",
    )


def _find_title_locations(
    title: str,
    *,
    bundle: ContextBundle,
) -> list[str]:
    """Where the title string appears in assembled context fields."""
    if not title:
        return []
    locations: list[str] = []

    map_module_idxs = [
        i for i, row in enumerate(bundle.track_map) if row.get("module") == title
    ]
    map_lesson_idxs = [
        i for i, row in enumerate(bundle.track_map) if row.get("lesson") == title
    ]
    if map_module_idxs:
        locations.append(f"track_map[].module (indices {map_module_idxs})")
    if map_lesson_idxs:
        locations.append(f"track_map[].lesson (indices {map_lesson_idxs})")

    for i, row in enumerate(bundle.unlocked_content):
        if row.get("module") == title:
            locations.append(f"unlocked_content[{i}].module")
        if title in (row.get("description") or ""):
            locations.append(f"unlocked_content[{i}].description")
        if row.get("lesson") == title:
            locations.append(f"unlocked_content[{i}].lesson")
        if title in (row.get("content") or ""):
            locations.append(f"unlocked_content[{i}].content")

    for i, row in enumerate(bundle.cohort_notes):
        if row.get("lesson") == title:
            locations.append(f"cohort_notes[{i}].lesson")
        for field in ("summary", "unclear_points", "knowledge_base"):
            if title in (row.get(field) or ""):
                locations.append(f"cohort_notes[{i}].{field}")

    if bundle.current_position:
        if bundle.current_position.get("track") == title:
            locations.append("current_position.track")
        if bundle.current_position.get("module") == title:
            locations.append("current_position.module")
        if bundle.current_position.get("lesson") == title:
            locations.append("current_position.lesson")

    if title in (bundle.track_guide or ""):
        locations.append("track_guide (texto do material_guide)")

    return locations


async def _load_titles(
    db: AsyncSession, cohort_id: uuid.UUID, lesson_id: uuid.UUID
) -> tuple[str, str, str]:
    cohort = await db.get(Cohort, cohort_id)
    if cohort is None:
        raise SystemExit(f"Cohort not found: {cohort_id}")

    track = (
        await db.execute(select(Track).where(Track.id == cohort.track_id))
    ).scalar_one()

    lesson = (
        await db.execute(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(selectinload(Lesson.module))
        )
    ).scalar_one_or_none()
    if lesson is None:
        raise SystemExit(f"Lesson not found: {lesson_id}")

    module: Module = lesson.module
    return track.title, module.title, lesson.title


async def run(
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_id: uuid.UUID,
    *,
    full: bool,
) -> None:
    async with SessionLocal() as db:
        student = await db.get(User, student_id)
        if student is None:
            raise SystemExit(f"Student not found: {student_id}")

        first_name = _first_name(student.name or "")
        track_title, module_title, lesson_title = await _load_titles(
            db, cohort_id, lesson_id
        )

        bundle = await ContextBuilder(db).build_lesson(
            cohort_id, lesson_id, student_id=student_id
        )
        system_blocks = bundle.to_system_blocks()
        blocks = _serialize_blocks(bundle)
        history = await lesson_conversation_history(
            db, cohort_id, student_id, lesson_id
        )

        # ---- 1) Header ----
        print("=" * 72)
        print("Lira context inspection (read-only)")
        print("=" * 72)
        print(f"cohort_id:  {cohort_id}")
        print(f"student_id: {student_id}  ({student.name!r} → first={first_name!r})")
        print(f"lesson_id:  {lesson_id}")
        print(f"track:      {track_title!r}")
        print(f"module:     {module_title!r}")
        print(f"lesson:     {lesson_title!r}")
        print(f"scope:      {bundle.scope}")
        print(
            f"track_map lessons: {len(bundle.track_map)}  |  "
            f"unlocked_content: {len(bundle.unlocked_content)}  |  "
            f"cohort_notes: {len(bundle.cohort_notes)}"
        )

        # ---- 2) Blocks content ----
        print("\n" + "=" * 72)
        print("1. BLOCOS MONTADOS (to_system_blocks / por seção)")
        print("=" * 72)
        for name in (
            "track_map",
            "unlocked_content",
            "cohort_notes",
            "current_position",
            "track_guide",
        ):
            _print_text(name, blocks[name], full=full)
        _print_text("to_system_blocks() [concatenado]", system_blocks, full=full)

        # ---- 3) Sizes ----
        print("\n" + "=" * 72)
        print("2. TAMANHOS EM CARACTERES")
        print("=" * 72)
        for name in (
            "track_map",
            "unlocked_content",
            "cohort_notes",
            "current_position",
            "track_guide",
        ):
            n = len(blocks[name])
            print(f"  {name:20s}  {n:>8,} chars  (~{_tokens(n):,} tokens)")

        total_blocks = len(system_blocks)
        print(f"  {'TOTAL blocos':20s}  {total_blocks:>8,} chars  (~{_tokens(total_blocks):,} tokens)")
        print("  (TOTAL = len(to_system_blocks()), fonte da verdade)")

        print("\n  unlocked_content — detalhe por item:")
        if not bundle.unlocked_content:
            print("    (nenhuma aula liberada)")
        for item in bundle.unlocked_content:
            if "description" in item:
                title = item.get("module") or "?"
                content_len = len(item.get("description") or "")
                print(
                    f"    - módulo {title!r}: description={content_len:,} chars "
                    f"(~{_tokens(content_len):,} tokens)"
                )
                continue
            title = item.get("lesson") or "?"
            content_len = len(item.get("content") or "")
            print(
                f"    - aula {title!r}: content={content_len:,} chars "
                f"(~{_tokens(content_len):,} tokens)"
            )

        print("\n  cohort_notes — detalhe por aula:")
        if not bundle.cohort_notes:
            print("    (nenhuma nota)")
        for item in bundle.cohort_notes:
            title = item.get("lesson") or "?"
            summary_n = len(item.get("summary") or "")
            unclear_n = len(item.get("unclear_points") or "")
            kb_n = len(item.get("knowledge_base") or "")
            print(
                f"    - {title!r}:\n"
                f"        summary={summary_n:,}  "
                f"unclear_points={unclear_n:,}  "
                f"knowledge_base={kb_n:,}  "
                f"(~{_tokens(summary_n + unclear_n + kb_n):,} tokens fields)"
            )

        # ---- 4) Voice instructions ----
        print("\n" + "=" * 72)
        print("3. INSTRUCTIONS COMPLETAS DO CANAL DE VOZ (sem truncar)")
        print("=" * 72)
        voice_full, breakdown = _assemble_voice_instructions(
            system_blocks=system_blocks,
            history=history,
            student_first_name=first_name,
        )
        voice_n = len(voice_full)
        print(f"  total:  {voice_n:,} chars  (~{_tokens(voice_n):,} tokens)")
        print(f"  limite: {INSTRUCTIONS_CHAR_LIMIT:,} chars (INSTRUCTIONS_CHAR_LIMIT)")
        print(f"  vs limite: {_limit_delta(voice_n)}")
        print(f"  history turns: {len(history)}")
        print("  breakdown:")
        for key, val in breakdown.items():
            print(f"    {key:40s}  {val:>8,} chars  (~{_tokens(val):,} tokens)")

        # ---- 5) Projection (new model: current catalog only; prior notes slim) ----
        print("\n" + "=" * 72)
        print("4. PROJEÇÃO — todas as aulas da trilha liberadas")
        print("=" * 72)
        n_total = len(bundle.track_map)
        n_unlocked = sum(1 for row in bundle.track_map if row.get("unlocked"))
        n_notes = len(bundle.cohort_notes)
        unlocked_block_len = len(blocks["unlocked_content"])
        notes_block_len = len(blocks["cohort_notes"])
        current_lesson_title = (
            (bundle.current_position or {}).get("lesson") if bundle.current_position else None
        )

        if n_unlocked == 0:
            print("  AVISO: nenhuma aula liberada — não é possível projetar conteúdo.")
            projected_unlocked = unlocked_block_len
            projected_notes = notes_block_len
            projected_system = total_blocks
            projected_voice = voice_n
            notes_model = "n/a"
        else:
            # Catalog is always current-lesson-only — does not grow with unlocks.
            projected_unlocked = unlocked_block_len
            projected_notes, notes_model = _project_cohort_notes_all_unlocked(
                cohort_notes=bundle.cohort_notes,
                current_lesson_title=current_lesson_title,
                n_total=n_total,
            )
            projected_system = (
                total_blocks
                - unlocked_block_len
                - notes_block_len
                + projected_unlocked
                + projected_notes
            )
            projected_voice = voice_n - total_blocks + projected_system

            print(f"  aulas na trilha (track_map): {n_total}")
            print(f"  aulas liberadas agora:       {n_unlocked}")
            print(f"  notas presentes agora:       {n_notes}")
            print("  modelo: unlocked_content = só aula atual (não escala);")
            print(f"          cohort_notes = {notes_model}")
            print()
            print("  tamanhos projetados (blocos):")
            print(
                f"    track_map          {len(blocks['track_map']):>8,}  (fixo — já inclui todas)"
            )
            print(
                f"    unlocked_content   {projected_unlocked:>8,}  "
                f"(fixo — só aula atual; agora {unlocked_block_len:,})"
            )
            print(
                f"    cohort_notes       {projected_notes:>8,}  "
                f"(agora {notes_block_len:,})"
            )
            print(
                f"    current_position   {len(blocks['current_position']):>8,}  (fixo)"
            )
            print(
                f"    track_guide        {len(blocks['track_guide']):>8,}  (fixo)"
            )
            print(
                f"    TOTAL blocos       {projected_system:>8,} chars  "
                f"(~{_tokens(projected_system):,} tokens)  "
                f"[agora {total_blocks:,}]"
            )
            print()
            print("  instructions de voz projetadas:")
            print(
                f"    total:  {projected_voice:,} chars  "
                f"(~{_tokens(projected_voice):,} tokens)"
            )
            print(f"    vs limite: {_limit_delta(projected_voice)}")

        # ---- 6) Title presence ----
        print("\n" + "=" * 72)
        print("5. TÍTULOS APARECEM NOS BLOCOS?")
        print("=" * 72)

        for label, title in (
            ("Trilha", track_title),
            ("Módulo", module_title),
            ("Aula", lesson_title),
        ):
            locs = _find_title_locations(title, bundle=bundle)
            if locs:
                print(f"  {label} ({title!r}): SIM")
                for loc in locs:
                    print(f"    - {loc}")
            else:
                print(f"  {label} ({title!r}): NÃO")

        print("\nDone.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect Lira context size for a cohort/student/lesson (read-only)."
    )
    parser.add_argument("--cohort-id", type=uuid.UUID, required=True)
    parser.add_argument("--student-id", type=uuid.UUID, required=True)
    parser.add_argument("--lesson-id", type=uuid.UUID, required=True)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print each block in full (default: first 500 chars)",
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            args.cohort_id,
            args.student_id,
            args.lesson_id,
            full=args.full,
        )
    )


if __name__ == "__main__":
    main()
