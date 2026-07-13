"""Assemble Realtime session instructions with cross-channel lesson history."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_openai
from app.ai.context_builder import ContextBuilder
from app.ai.engine import SYSTEM_BASE
from app.core.config import settings
from app.services.conversation_service import merged_lesson_history

INSTRUCTIONS_CHAR_LIMIT = 25_000
MAX_HISTORY_TURNS = 20

VOICE_MODE_BLOCK = """## Modo de conversa
Você está em uma chamada de voz ao vivo. Respostas curtas e naturais para fala.
Não use markdown, listas longas ou formatação. Uma ideia por vez."""

OPENING_BLOCK = """## Abertura
Cumprimente o aluno pelo nome e retome de onde a conversa parou.
Não recomece do zero se já houve troca de mensagens."""


def format_history(history: list[dict]) -> str:
    if not history:
        return "(nenhuma mensagem anterior)"
    lines: list[str] = []
    for msg in history:
        role = "Aluno" if msg.get("role") == "user" else "Lira"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(nenhuma mensagem anterior)"


async def _summarize_dropped_turns(dropped: list[dict]) -> str:
    if not dropped:
        return ""
    transcript = format_history(dropped)
    if len(transcript) > 12_000:
        transcript = transcript[-12_000:]

    client = get_openai()
    resp = await client.chat.completions.create(
        model=settings.ENGINE_MODEL,
        max_tokens=512,
        messages=[
            {
                "role": "system",
                "content": (
                    "Resuma em português do Brasil, em poucos parágrafos curtos, "
                    "o que foi discutido nesta conversa de aula. Foque no que o aluno "
                    "já demonstrou entender e nos tópicos em aberto."
                ),
            },
            {"role": "user", "content": transcript},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


class RealtimeInstructionsBuilder:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def build(
        self,
        *,
        cohort_id: uuid.UUID,
        lesson_id: uuid.UUID,
        student_id: uuid.UUID,
        student_first_name: str,
    ) -> str:
        bundle = await ContextBuilder(self._db).build_lesson(cohort_id, lesson_id)
        system_blocks = bundle.to_system_blocks()
        history = await merged_lesson_history(self._db, cohort_id, student_id, lesson_id)

        return await self._assemble(
            system_blocks=system_blocks,
            history=history,
            student_first_name=student_first_name,
        )

    async def _assemble(
        self,
        *,
        system_blocks: str,
        history: list[dict],
        student_first_name: str,
    ) -> str:
        opening = OPENING_BLOCK.replace(
            "Cumprimente o aluno pelo nome",
            f"Cumprimente o aluno pelo nome ({student_first_name})",
        )
        base_prefix = f"{SYSTEM_BASE}\n\n{system_blocks}\n\n{VOICE_MODE_BLOCK}\n\n"

        def render(hist_block: str, summary: str = "") -> str:
            summary_block = ""
            if summary:
                summary_block = f"## Resumo da conversa anterior\n{summary}\n\n"
            return (
                f"{base_prefix}"
                f"{summary_block}"
                f"## Histórico da conversa desta aula\n{hist_block}\n\n"
                f"{opening}"
            )

        full = render(format_history(history))
        if len(full) <= INSTRUCTIONS_CHAR_LIMIT:
            return full

        recent = history[-MAX_HISTORY_TURNS:]
        dropped = history[:-MAX_HISTORY_TURNS]
        truncated = render(format_history(recent))
        if len(truncated) <= INSTRUCTIONS_CHAR_LIMIT:
            return truncated

        summary = await _summarize_dropped_turns(dropped)
        with_summary = render(format_history(recent), summary=summary)
        if len(with_summary) <= INSTRUCTIONS_CHAR_LIMIT:
            return with_summary

        return truncated
