"""Parse provider message ids from Cinndi send responses."""

from __future__ import annotations

import json
from typing import Any


def provider_message_id_from_response(body: str) -> str | None:
    raw = (body or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return _extract_from_hash(parsed)


def _extract_from_hash(parsed: Any) -> str | None:
    if not isinstance(parsed, dict):
        return None
    candidates = [
        parsed.get("id"),
        parsed.get("message_id"),
        parsed.get("messageId"),
        (parsed.get("mensagem") or {}).get("id")
        if isinstance(parsed.get("mensagem"), dict)
        else None,
        (parsed.get("data") or {}).get("id") if isinstance(parsed.get("data"), dict) else None,
        (parsed.get("result") or {}).get("id") if isinstance(parsed.get("result"), dict) else None,
        (parsed.get("message") or {}).get("id") if isinstance(parsed.get("message"), dict) else None,
        (parsed.get("dados") or {}).get("id_mensagem")
        if isinstance(parsed.get("dados"), dict)
        else None,
        (parsed.get("dados") or {}).get("id") if isinstance(parsed.get("dados"), dict) else None,
    ]
    for candidate in candidates:
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return None
