from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(subject: str, role: str, token_type: TokenType, expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject, role, "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str, role: str) -> str:
    return _create_token(
        subject, role, "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Decodifica e valida o token. Lança jwt.InvalidTokenError em qualquer falha."""
    payload = jwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload
