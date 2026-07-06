"""Brazilian phone normalization — E.164 digits without '+' (Cinndi/WhatsApp)."""

from __future__ import annotations

import re

_DIGITS = re.compile(r"\D")
VALID_BR_DDD = frozenset(str(d) for d in range(11, 100))


def digits_only(raw: str | None) -> str:
    if raw is None:
        return ""
    return _DIGITS.sub("", str(raw).strip())


def _valid_brazilian_local(local: str) -> bool:
    if len(local) not in (10, 11):
        return False
    if local[:2] not in VALID_BR_DDD:
        return False
    if len(local) == 11 and local[2] != "9":
        return False
    return True


def _normalize_with_country_code(digits: str) -> str:
    ddd_and_number = digits[2:]
    if len(ddd_and_number) == 10:
        return f"55{ddd_and_number[:2]}9{ddd_and_number[2:]}"
    return digits


def _normalize_without_country_code(digits: str) -> str:
    if len(digits) == 10:
        return f"55{digits[:2]}9{digits[2:]}"
    return f"55{digits}"


def normalize_br_phone(raw: str | None) -> str | None:
    """Return canonical BR/international digits (no '+') or None if invalid."""
    if raw is None:
        return None
    digits = digits_only(raw)
    if not digits:
        return None

    if digits.startswith("55") and len(digits) in (12, 13):
        normalized = _normalize_with_country_code(digits)
    elif _valid_brazilian_local(digits):
        normalized = _normalize_without_country_code(digits)
    elif len(digits) >= 10:
        normalized = digits
    else:
        return None

    if normalized.startswith("55") and len(normalized) in (12, 13):
        if not _valid_brazilian_local(normalized[2:]):
            return None

    if len(normalized) < 10 or len(normalized) > 15:
        return None
    return normalized


def phone_lookup_variants(raw: str | None) -> list[str]:
    """Candidate stored values for inbound phone matching (with/without mobile 9)."""
    canonical = normalize_br_phone(raw)
    if not canonical:
        return []

    seen: set[str] = set()
    out: list[str] = []

    def add(value: str | None) -> None:
        if value and value not in seen:
            seen.add(value)
            out.append(value)

    add(canonical)
    add(digits_only(raw))

    if canonical.startswith("55") and len(canonical) == 13 and canonical[4] == "9":
        without_ninth = f"{canonical[:4]}{canonical[5:]}"
        add(without_ninth)

    if canonical.startswith("55") and len(canonical) == 12:
        national = canonical[2:]
        if len(national) == 10:
            with_ninth = f"55{national[:2]}9{national[2:]}"
            add(with_ninth)

    return out


def mask_phone_br(digits: str | None) -> str:
    """Display mask for BR mobile: (11) 98765-4321."""
    d = digits_only(digits)
    if not d:
        return ""
    if d.startswith("55") and len(d) >= 12:
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return d
