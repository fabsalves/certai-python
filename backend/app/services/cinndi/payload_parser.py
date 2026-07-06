"""Parse Cinndi webhook payloads into normalized structures."""

from __future__ import annotations

from typing import Any

from app.core.phone import digits_only
from app.services.cinndi.types import CinndiAck, CinndiMessage, CinndiParseResult, as_dict

ACK_STATUS_MAP: dict[int, str] = {
    0: "failed",
    1: "sent",
    2: "delivered",
    3: "read",
}


def parse_payload(payload: dict[str, Any]) -> CinndiParseResult:
    data = as_dict(payload)
    tipo = str(data.get("tipo") or "").strip().lower()
    channel_phone = digits_only(str(data.get("numero") or data.get("origem") or ""))
    origin_phone = digits_only(str(data.get("origem") or ""))

    if tipo == "mensagem":
        return _parse_message(channel_phone, origin_phone, data)
    if tipo == "ack":
        return _parse_ack(channel_phone, origin_phone, data)
    return CinndiParseResult(type="unknown", channel_phone=channel_phone, origin_phone=origin_phone)


def _parse_message(
    channel_phone: str, origin_phone: str, data: dict[str, Any]
) -> CinndiParseResult:
    raw = as_dict(data.get("mensagem"))
    media = as_dict(raw.get("media"))
    message = CinndiMessage(
        body=_resolved_body(raw),
        from_phone=digits_only(str(raw.get("from") or "")),
        message_id=str(raw.get("id") or "").strip(),
        message_type=str(raw.get("type") or "").strip(),
        self_direction=str(raw.get("self") or "").strip(),
        caption=str(raw.get("caption") or "").strip(),
        url_arquivo=str(media.get("urlArquivo") or raw.get("urlArquivo") or "").strip(),
        media_data=str(media.get("data") or "").strip(),
        media_mimetype=str(media.get("mimetype") or "").strip(),
        media_filename=str(media.get("filename") or "").strip(),
        to_phone=digits_only(str(raw.get("to") or "")),
        author=str(raw.get("author") or "").strip(),
    )
    return CinndiParseResult(
        type="mensagem",
        channel_phone=channel_phone,
        origin_phone=origin_phone,
        message=message,
    )


def _parse_ack(
    channel_phone: str, origin_phone: str, data: dict[str, Any]
) -> CinndiParseResult:
    raw = as_dict(data.get("ack"))
    ack_code = int(raw.get("ack") or 0)
    ack = CinndiAck(
        message_id=str(raw.get("id") or "").strip(),
        ack_code=ack_code,
        status=ACK_STATUS_MAP.get(ack_code, "sent"),
        to_phone=digits_only(str(raw.get("to") or "")),
        from_phone=digits_only(str(raw.get("from") or "")),
    )
    return CinndiParseResult(
        type="ack",
        channel_phone=channel_phone,
        origin_phone=origin_phone,
        ack=ack,
    )


def _resolved_body(msg: dict[str, Any]) -> str:
    text = str(msg.get("body") or "").strip()
    if text:
        return text
    msg_type = str(msg.get("type") or "")
    if msg_type not in {"button", "interactive"}:
        return ""
    for key in ("selectedDisplayText", "buttonText", "title"):
        cleaned = str(msg.get(key) or "").strip()
        if cleaned:
            return cleaned
    return ""
