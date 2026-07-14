"""Realtime GA tool schemas — ported from app.ai.tools (Chat Completions format)."""

from __future__ import annotations

from typing import Any

from app.ai.tools import TOOL_SCHEMAS

# Server-executed via POST /realtime/tools/{name}
SERVER_TOOL_NAMES = frozenset({"score_understanding", "escalate_scope"})

END_CONVERSATION_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "end_conversation",
    "description": (
        "Sinal técnico para o app encerrar a call. NÃO é despedida — nunca use esta ferramenta "
        "como veículo de despedida.\n"
        "Ordem obrigatória: (1) pelo menos duas insistências acolhedoras se o aluno quiser sair; "
        "(2) se ele mantiver a decisão, conduza o fechamento, avise que vai encerrar e fale a "
        "despedida completa em voz num turno só de conversa, SEM chamar esta ferramenta; "
        "(3) somente no movimento SEGUINTE, depois de já ter falado a despedida em voz, "
        "chame end_conversation (tool only, sem nova fala longa).\n"
        "Chamar esta ferramenta antes de ter falado a despedida em voz, ou no mesmo turno "
        "em que ainda não despediu de fato, é incorreto."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _chat_schema_to_realtime(schema: dict[str, Any]) -> dict[str, Any]:
    fn = schema.get("function") or {}
    return {
        "type": "function",
        "name": fn["name"],
        "description": fn.get("description", ""),
        "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
    }


def realtime_tool_schemas() -> list[dict[str, Any]]:
    """Schemas for OpenAI Realtime client_secrets (GA format, no humanizer tools)."""
    ported = [_chat_schema_to_realtime(schema) for schema in TOOL_SCHEMAS]
    return [*ported, END_CONVERSATION_TOOL]
