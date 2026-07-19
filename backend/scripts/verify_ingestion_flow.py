"""Smoke checks for the AI ingestion flow (no OpenAI/DB required)."""

from __future__ import annotations

import io
import inspect
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend package is importable when run as a script.
sys.path.insert(0, ".")

from app.ai.context_builder import ContextBundle
from app.services.ingestion.extraction import UnsupportedFormatError, extract_text
from app.services.lesson_completion_service import complete_lesson


def test_extraction_txt() -> None:
    assert extract_text("Olá, turma".encode(), ".txt") == "Olá, turma"


def test_extraction_docx() -> None:
    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Conceito central da aula")
    doc.save(buf)
    text = extract_text(buf.getvalue(), ".docx")
    assert "Conceito central da aula" in text


def test_unsupported_ppt_raises() -> None:
    try:
        extract_text(b"fake", ".ppt")
        raise AssertionError("expected UnsupportedFormatError")
    except UnsupportedFormatError:
        pass


def test_context_bundle_track_guide_block() -> None:
    bundle = ContextBundle(scope="lesson", track_guide="## Objetivo macro")
    blocks = bundle.to_system_blocks()
    assert "## Track guide" in blocks
    assert "Objetivo macro" in blocks


def test_context_bundle_empty_guide_omitted() -> None:
    bundle = ContextBundle(scope="lesson", track_guide="  ")
    assert "## Track guide" not in bundle.to_system_blocks()


def test_complete_lesson_enqueues_ingestion_not_dispatch() -> None:
    """Fast path must enqueue ingest_lesson_completion, never plan_dispatch."""
    source = inspect.getsource(complete_lesson)
    assert "ingest_lesson_completion" in source
    assert "plan_dispatch" not in source


def test_ingest_task_chains_dispatch_after_commit() -> None:
    from app.workers import tasks

    source = inspect.getsource(tasks._ingest_lesson_completion)
    assert "await db.commit()" in source
    assert "plan_dispatch.delay" in source
    # Dispatch must come after commit in source order.
    assert source.index("await db.commit()") < source.index("plan_dispatch.delay")


def test_coerce_llm_text_field_serializes_nested_values() -> None:
    from app.services.ingestion import coerce_llm_text_field

    assert coerce_llm_text_field("texto") == "texto"
    assert coerce_llm_text_field({"tema": "x"}) == '{"tema": "x"}'
    assert coerce_llm_text_field(["a", "b"]) == '["a", "b"]'
    assert coerce_llm_text_field(None) == ""


async def _test_ingest_lesson_note_coerces_dict_fields() -> None:
    from app.services.ingestion.lesson_note_ingestion_service import ingest_lesson_note
    from app.models.assessment import CohortLessonNote

    note = CohortLessonNote(
        cohort_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        lesson_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        professor_transcript="A turma entendeu X",
        ingestion_status="pending",
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=note)
    db.flush = AsyncMock()

    nested_kb = {"conceitos": ["fato", "interpretação"], "perguntas": ["o que é fato?"]}

    with (
        patch(
            "app.services.ingestion.lesson_note_ingestion_service.consolidate_notes",
            new=AsyncMock(
                return_value={
                    "summary": {"titulo": "Resumo"},
                    "unclear_points": ["dúvida 1"],
                    "knowledge_base": nested_kb,
                }
            ),
        ),
        patch(
            "app.services.ingestion.lesson_note_ingestion_service.get_storage",
            return_value=MagicMock(),
        ),
    ):
        result = await ingest_lesson_note(db, note.id)

    import json

    assert isinstance(result.summary, str)
    assert isinstance(result.unclear_points, str)
    assert isinstance(result.attachment_knowledge_base, str)
    assert json.loads(result.attachment_knowledge_base) == nested_kb
    assert result.ingestion_status == "done"


async def _test_ingest_lesson_note_persists_fields() -> None:
    from app.services.ingestion.lesson_note_ingestion_service import ingest_lesson_note
    from app.models.assessment import CohortLessonNote

    note = CohortLessonNote(
        cohort_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        lesson_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        professor_transcript="A turma entendeu X",
        ingestion_status="pending",
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=note)
    db.flush = AsyncMock()

    with (
        patch(
            "app.services.ingestion.lesson_note_ingestion_service.consolidate_notes",
            new=AsyncMock(
                return_value={
                    "summary": "Resumo",
                    "unclear_points": "Dúvidas",
                    "knowledge_base": "Base",
                }
            ),
        ),
        patch(
            "app.services.ingestion.lesson_note_ingestion_service.get_storage",
            return_value=MagicMock(),
        ),
    ):
        result = await ingest_lesson_note(db, note.id)

    assert result.summary == "Resumo"
    assert result.attachment_knowledge_base == "Base"
    assert result.ingestion_status == "done"


def main() -> None:
    test_extraction_txt()
    test_extraction_docx()
    test_unsupported_ppt_raises()
    test_context_bundle_track_guide_block()
    test_context_bundle_empty_guide_omitted()
    test_complete_lesson_enqueues_ingestion_not_dispatch()
    test_ingest_task_chains_dispatch_after_commit()
    test_coerce_llm_text_field_serializes_nested_values()

    import asyncio

    asyncio.run(_test_ingest_lesson_note_coerces_dict_fields())
    asyncio.run(_test_ingest_lesson_note_persists_fields())
    print("verify_ingestion_flow: all checks passed")


if __name__ == "__main__":
    main()
