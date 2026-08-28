import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import settings

# Ambiguous characters omitted so the password is readable when copied once.
_PASSWORD_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_PASSWORD_LOWER = "abcdefghijkmnopqrstuvwxyz"
_PASSWORD_DIGIT = "23456789"
_PASSWORD_ALPHABET = _PASSWORD_UPPER + _PASSWORD_LOWER + _PASSWORD_DIGIT
_PASSWORD_LENGTH = 10


def generate_password() -> str:
    """Random initial password for staff. Meets upper/lower/digit; shown once."""
    chars = [
        secrets.choice(_PASSWORD_UPPER),
        secrets.choice(_PASSWORD_LOWER),
        secrets.choice(_PASSWORD_DIGIT),
        *[secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH - 3)],
    ]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(
    subject: str,
    role: str,
    token_type: TokenType,
    expires: timedelta,
    *,
    org: str = "",
    token_version: int = 0,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "org": org,
        "tv": int(token_version),
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str, *, org: str = "", token_version: int = 0) -> str:
    return _create_token(
        subject, role, "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        org=org,
        token_version=token_version,
    )


def create_refresh_token(subject: str, role: str, *, org: str = "", token_version: int = 0) -> str:
    return _create_token(
        subject, role, "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        org=org,
        token_version=token_version,
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Decodifica e valida o token. Lança jwt.InvalidTokenError em qualquer falha."""
    payload = jwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def token_version_matches(claims: dict[str, Any], user_token_version: int) -> bool:
    try:
        claim_tv = int(claims.get("tv", 0))
    except (TypeError, ValueError):
        return False
    return claim_tv == int(user_token_version or 0)
