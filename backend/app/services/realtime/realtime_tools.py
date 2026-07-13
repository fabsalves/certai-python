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
        "When the student says goodbye or wants to hang up: say a brief farewell first, "
        "then call this tool so the app disconnects the call."
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
