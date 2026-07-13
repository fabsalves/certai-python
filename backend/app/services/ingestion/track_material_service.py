"""Track material ingestion -- turns the attached PDF/PPTX into a track guide.

The guide is a MACRO reference (purpose, competencies, theme map, conversation
guidance) available to the AI in any lesson at any time. It intentionally avoids
lesson-by-lesson detail so it never teaches ahead of the cohort ("don't teach
the future" stays structural).
"""

import json
import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_openai
from app.core.config import settings
from app.models.track import Track
from app.services.ingestion import (
    INGESTION_DONE,
    INGESTION_FAILED,
    INGESTION_PROCESSING,
    INGESTION_UNSUPPORTED,
)
from app.services.ingestion.extraction import UnsupportedFormatError, extract_text
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

TRACK_GUIDE_SYSTEM_PROMPT = (
    "You will receive the extracted text of the support material attached to a "
    "learning track. Produce a JSON object with a single key 'guide' whose value "
    "is ONE string (Markdown sections allowed), written in Brazilian Portuguese. "
    "The guide is a macro reference the AI tutor consults during any lesson of "
    "this track: the track's overall purpose, the core competencies it develops, "
    "a map of the main themes and how they connect, and guidance on how to "
    "conduct conversations about them (useful vocabulary, analogies, and open "
    "questions that help probe the student's understanding). Do not reproduce "
    "lesson content in detail -- keep it macro, so it never teaches ahead of "
    "where the cohort is. Be neutral and descriptive, never judgemental or "
    "moralizing. Reply with the JSON only."
)


async def build_track_guide(extracted_text: str) -> str:
    """One LLM pass: raw material text -> macro guide in pt-BR."""
    if not extracted_text.strip():
        return ""
    client = get_openai()
    resp = await client.chat.completions.create(
        model=settings.ENGINE_MODEL,
        max_tokens=2048,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TRACK_GUIDE_SYSTEM_PROMPT},
            {"role": "user", "content": extracted_text},
        ],
    )
    text = resp.choices[0].message.content or ""
    try:
        guide = json.loads(text).get("guide", "")
    except json.JSONDecodeError:
        return text
    if isinstance(guide, str):
        return guide
    # Model ignored the "one string" instruction: keep valid JSON, not a dict repr.
    return json.dumps(guide, ensure_ascii=False, indent=2)


async def ingest_track_material(db: AsyncSession, track_id: uuid.UUID) -> Track:
    track = await db.get(Track, track_id)
    if track is None:
        raise ValueError("Trilha não encontrada")
    if not track.material_storage_key:
        raise ValueError("A trilha não possui material anexado")

    track.material_ingestion_status = INGESTION_PROCESSING
    await db.flush()

    content = await get_storage().open(track.material_storage_key)
    extension = Path(track.material_storage_key).suffix
    try:
        extracted = extract_text(content, extension)
    except UnsupportedFormatError:
        logger.warning("track %s: material without text extractor (%s)", track_id, extension)
        track.material_extracted_text = ""
        track.material_guide = ""
        track.material_ingestion_status = INGESTION_UNSUPPORTED
        await db.flush()
        return track

    track.material_extracted_text = extracted
    track.material_guide = await build_track_guide(extracted)
    track.material_ingestion_status = INGESTION_DONE
    await db.flush()
    return track


async def mark_track_material_failed(db: AsyncSession, track_id: uuid.UUID) -> None:
    track = await db.get(Track, track_id)
    if track is not None:
        track.material_ingestion_status = INGESTION_FAILED
        await db.flush()
