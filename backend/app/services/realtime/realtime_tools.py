"""Realtime GA tool schemas — ported from app.ai.tools (Chat Completions format)."""

from __future__ import annotations

from typing import Any

from app.ai.tools import TOOL_SCHEMAS

# Server-executed via POST /realtime/tools/{name}
SERVER_TOOL_NAMES = frozenset({
    "score_understanding",
    "escalate_scope",
    "request_session_link",
    "conclude_lesson",
})

END_CONVERSATION_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "end_conversation",
    "description": (
        "Sinal técnico para o app encerrar a call. NÃO é a despedida — fale em voz neste "
        "response e chame esta tool no mesmo response; o app só desliga depois que o áudio "
        "terminar (ack da tool + output_audio_buffer.stopped).\n"
        "A) Aluno pediu com clareza para sair e insistiu — nunca invente saída. Mesmo "
        "response: despedida completa em voz + esta tool.\n"
        "B) Fim da aula: mesmo response da despedida final: conclude_lesson + esta tool "
        "(com a fala de despedida).\n"
        "Sem esta tool a call fica aberta. Não use só por despedida antiga no histórico."
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
