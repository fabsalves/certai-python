"""Normalized Cinndi webhook structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class CinndiMessage:
    body: str
    from_phone: str
    message_id: str
    message_type: str
    self_direction: str
    caption: str = ""
    url_arquivo: str = ""
    media_data: str = ""
    media_mimetype: str = ""
    media_filename: str = ""
    to_phone: str = ""
    author: str = ""


@dataclass(frozen=True)
class CinndiAck:
    message_id: str
    ack_code: int
    status: str
    to_phone: str = ""
    from_phone: str = ""
    from_me: bool | None = None
    timestamp: int | None = None


@dataclass(frozen=True)
class CinndiParseResult:
    type: Literal["mensagem", "ack", "unknown"]
    channel_phone: str
    origin_phone: str
    message: CinndiMessage | None = None
    ack: CinndiAck | None = None

    @property
    def is_inbound_chat(self) -> bool:
        if self.type != "mensagem" or self.message is None:
            return False
        if self.message.self_direction.strip().lower() != "in":
            return False
        return self.message.message_type.lower() in {
            "chat",
            "audio",
            "ptt",
            "button",
            "interactive",
        }

    @property
    def is_ack(self) -> bool:
        return self.type == "ack" and self.ack is not None


def as_dict(payload: dict[str, Any] | Any) -> dict[str, Any]:
    if hasattr(payload, "items"):
        return dict(payload)
    return {}
