"""Rate cards: USD per 1M tokens (or per unit) by provider/model/cost_kind.

Costs are estimated at ingest and frozen on each usage event. Editing this file
does not rewrite history -- `AiUsageEvent.raw` keeps the provider payload so a
re-pricing pass is always possible.

A model with no known rate yields **None**, never 0: an unpriced model must show
up as a declared gap, not as free.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

# --- OpenAI Realtime (voice) -------------------------------------------------
# Audio dominates the bill: ~8x text, and fresh audio is ~80x cached audio.
_REALTIME_2 = {
    "realtime_audio_in": Decimal("32.00"),
    "realtime_audio_out": Decimal("64.00"),
    "realtime_text_in": Decimal("4.00"),
    "realtime_text_out": Decimal("24.00"),
    "realtime_audio_in_cached": Decimal("0.40"),
    "realtime_text_in_cached": Decimal("0.40"),
    "realtime_image_in": Decimal("5.00"),
    "realtime_image_in_cached": Decimal("0.50"),
}

# --- OpenAI ASR (input transcription during a call) --------------------------
# gpt-4o-mini-transcribe is sold per minute (~$0.003). At ~10 audio tokens per
# second that is ~600 tokens/min -> ~$5.00 / 1M audio tokens.
_TRANSCRIBE_MINI = {
    "transcribe_audio_in": Decimal("5.00"),
    "transcribe_text_in": Decimal("0.60"),
    "transcribe_text_out": Decimal("0.60"),
}

# --- OpenAI Chat Completions (engine, humanizer, evaluator, ingestion) ------
_CHAT_4O = {
    "chat_text_in": Decimal("2.50"),
    "chat_text_cached_in": Decimal("1.25"),
    "chat_text_out": Decimal("10.00"),
}

_CHAT_4O_MINI = {
    "chat_text_in": Decimal("0.15"),
    "chat_text_cached_in": Decimal("0.075"),
    "chat_text_out": Decimal("0.60"),
}

OPENAI_RATES: dict[str, dict[str, Decimal]] = {
    "gpt-realtime-2": _REALTIME_2,
    "gpt-realtime": _REALTIME_2,
    "gpt-4o-mini-transcribe": _TRANSCRIBE_MINI,
    "gpt-4o-transcribe": {
        "transcribe_audio_in": Decimal("6.00"),
        "transcribe_text_in": Decimal("2.50"),
        "transcribe_text_out": Decimal("10.00"),
    },
    # Order matters for the prefix fallback: gpt-4o-mini before gpt-4o.
    "gpt-4o-mini": _CHAT_4O_MINI,
    "gpt-4o": _CHAT_4O,
}

# --- Groq (professor report transcription) ----------------------------------
# Whisper is billed per audio hour, not per token.
GROQ_RATES: dict[str, dict[str, Decimal]] = {
    "whisper-large-v3": {"transcribe_audio_seconds": Decimal("0.111")},
    "whisper-large-v3-turbo": {"transcribe_audio_seconds": Decimal("0.04")},
}

_RATE_CARDS: dict[str, Mapping[str, Mapping[str, Decimal]]] = {
    "openai": OPENAI_RATES,
    "groq": GROQ_RATES,
}

# Kinds billed per second of audio instead of per 1M tokens.
_PER_HOUR_KINDS = frozenset({"transcribe_audio_seconds"})

_SECONDS_PER_HOUR = Decimal("3600")
_ONE_MILLION = Decimal("1000000")


def get_rate_usd(provider: str, model: str, cost_kind: str) -> Decimal | None:
    """Rate for a (provider, model, kind), or None when unknown.

    Falls back to family prefixes so a new point release (gpt-realtime-2.1)
    prices against its family instead of silently dropping to no rate.
    """
    card = _RATE_CARDS.get(provider, {})
    model_rates = card.get(model)
    if model_rates is None:
        for key, rates in card.items():
            if model.startswith(key):
                model_rates = rates
                break
    if model_rates is None:
        return None
    return model_rates.get(cost_kind)


def estimate_cost_usd(
    *,
    provider: str,
    model: str,
    cost_kind: str,
    quantity: Decimal,
    unit: str = "tokens",
) -> Decimal | None:
    """Estimated USD for a quantity, or **None** when there is no known rate.

    Returning None (and not 0) is deliberate: the read side counts these as
    `unpriced_events` and warns that the displayed total is incomplete.
    """
    rate = get_rate_usd(provider, model, cost_kind)
    if rate is None:
        return None
    if quantity <= 0:
        return Decimal("0.000000")

    if cost_kind in _PER_HOUR_KINDS:
        if unit != "seconds":
            return None
        return (quantity * rate / _SECONDS_PER_HOUR).quantize(Decimal("0.000001"))

    if unit != "tokens":
        return None
    return (quantity * rate / _ONE_MILLION).quantize(Decimal("0.000001"))
