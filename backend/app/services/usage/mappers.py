"""Map provider usage payloads into normalized cost lines.

Each provider reports usage in its own shape. The mappers here turn those into
`UsageLine`s keyed by `cost_kind`, which is the only vocabulary the rate card and
the read side know about.

Every mapper subtracts cached tokens from the fresh totals: providers report
cached tokens *inside* the input total, and billing them at the fresh rate would
overstate the cost by up to 80x on voice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class UsageLine:
    cost_kind: str
    quantity: Decimal
    unit: str = "tokens"


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _collect(pairs: list[tuple[str, Decimal]], unit: str = "tokens") -> list[UsageLine]:
    return [
        UsageLine(cost_kind=kind, quantity=qty, unit=unit)
        for kind, qty in pairs
        if qty > 0
    ]


def map_openai_realtime_response(usage: dict[str, Any] | None) -> list[UsageLine]:
    """Split `response.done` usage into billable kinds (fresh vs cached)."""
    if not usage:
        return []

    details = usage.get("input_token_details") or usage.get("input_tokens_details") or {}
    cached = details.get("cached_tokens_details") or {}
    out = usage.get("output_token_details") or usage.get("output_tokens_details") or {}

    text_in = _dec(details.get("text_tokens"))
    audio_in = _dec(details.get("audio_tokens"))
    image_in = _dec(details.get("image_tokens"))
    cached_text = _dec(cached.get("text_tokens"))
    cached_audio = _dec(cached.get("audio_tokens"))
    cached_image = _dec(cached.get("image_tokens"))

    # Prefer the modality breakdown; fall back to totals when the API omits it.
    # text_in must stay the GROSS total here: the cached share is subtracted
    # once, below. Pre-subtracting it would zero out the fresh line entirely.
    if text_in == 0 and audio_in == 0 and image_in == 0:
        text_in = _dec(usage.get("input_tokens"))
        cached_text = _dec(details.get("cached_tokens"))

    zero = Decimal("0")
    lines = _collect(
        [
            ("realtime_text_in", max(zero, text_in - cached_text)),
            ("realtime_audio_in", max(zero, audio_in - cached_audio)),
            ("realtime_image_in", max(zero, image_in - cached_image)),
            ("realtime_text_in_cached", cached_text),
            ("realtime_audio_in_cached", cached_audio),
            ("realtime_image_in_cached", cached_image),
            ("realtime_text_out", _dec(out.get("text_tokens"))),
            ("realtime_audio_out", _dec(out.get("audio_tokens"))),
        ]
    )

    # Fallback when output_token_details is missing entirely.
    if not any(line.cost_kind.endswith("_out") for line in lines):
        lines.extend(_collect([("realtime_text_out", _dec(usage.get("output_tokens")))]))

    return lines


def map_openai_transcription(usage: dict[str, Any] | None) -> list[UsageLine]:
    """Split `input_audio_transcription.completed` usage onto the ASR rate card."""
    if not usage:
        return []

    # Duration-based ASR: convert to token-equivalents (~10 audio tokens/second)
    # so it prices against the same transcribe_audio_in rate.
    if usage.get("type") == "duration":
        seconds = _dec(usage.get("seconds"))
        if seconds <= 0:
            return []
        return _collect(
            [
                (
                    "transcribe_audio_in",
                    (seconds * Decimal("10")).quantize(Decimal("0.001")),
                )
            ]
        )

    details = usage.get("input_token_details") or usage.get("input_tokens_details") or {}
    audio_in = _dec(details.get("audio_tokens"))
    text_in = _dec(details.get("text_tokens"))
    text_out = _dec(usage.get("output_tokens"))

    if audio_in == 0 and text_in == 0:
        audio_in = _dec(usage.get("input_tokens"))

    return _collect(
        [
            ("transcribe_audio_in", audio_in),
            ("transcribe_text_in", text_in),
            ("transcribe_text_out", text_out),
        ]
    )


def map_openai_chat_completion(usage: dict[str, Any] | None) -> list[UsageLine]:
    """Split Chat Completions usage (engine, humanizer, evaluator, ingestion)."""
    if not usage:
        return []

    prompt = _dec(usage.get("prompt_tokens")) or _dec(usage.get("input_tokens"))
    completion = _dec(usage.get("completion_tokens")) or _dec(
        usage.get("output_tokens")
    )
    details = (
        usage.get("prompt_tokens_details")
        or usage.get("input_token_details")
        or usage.get("input_tokens_details")
        or {}
    )
    cached = _dec(details.get("cached_tokens"))

    return _collect(
        [
            ("chat_text_in", max(Decimal("0"), prompt - cached)),
            ("chat_text_cached_in", cached),
            ("chat_text_out", completion),
        ]
    )


def map_groq_transcription_seconds(seconds: float | Decimal | None) -> list[UsageLine]:
    """Groq/Whisper bills per audio hour, so the unit is seconds, not tokens."""
    quantity = _dec(seconds)
    if quantity <= 0:
        return []
    return _collect(
        [("transcribe_audio_seconds", quantity.quantize(Decimal("0.001")))],
        unit="seconds",
    )
