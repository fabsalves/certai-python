"""Password strength rules for new / changed passwords (existing hashes stay valid)."""
from __future__ import annotations

import re

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

PASSWORD_RULES_DETAIL = (
    "A senha deve ter pelo menos 10 caracteres, com letra maiúscula, "
    "minúscula e número."
)

_HAS_LOWER = re.compile(r"[a-z]")
_HAS_UPPER = re.compile(r"[A-Z]")
_HAS_DIGIT = re.compile(r"\d")


def validate_new_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(PASSWORD_RULES_DETAIL)
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"A senha deve ter no máximo {MAX_PASSWORD_LENGTH} caracteres.")
    if not _HAS_LOWER.search(password):
        raise ValueError(PASSWORD_RULES_DETAIL)
    if not _HAS_UPPER.search(password):
        raise ValueError(PASSWORD_RULES_DETAIL)
    if not _HAS_DIGIT.search(password):
        raise ValueError(PASSWORD_RULES_DETAIL)
    return password
