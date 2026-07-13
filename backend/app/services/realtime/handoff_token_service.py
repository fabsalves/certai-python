"""JWT handoff tokens for public voice session links (48h, reusable)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings

TOKEN_TYPE = "voice_handoff"


class HandoffTokenError(Exception):
    def __init__(self, message: str, *, expired: bool = False) -> None:
        super().__init__(message)
        self.expired = expired


@dataclass(frozen=True)
class HandoffClaims:
    user_id: uuid.UUID
    cohort_id: uuid.UUID
    lesson_id: uuid.UUID
    conversation_id: uuid.UUID | None
    jti: str
    expires_at: datetime


class HandoffTokenService:
    def __init__(self) -> None:
        self._expire_hours = settings.VOICE_HANDOFF_EXPIRE_HOURS

    def generate(
        self,
        *,
        user_id: uuid.UUID,
        cohort_id: uuid.UUID,
        lesson_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> tuple[str, datetime]:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self._expire_hours)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "cohort_id": str(cohort_id),
            "lesson_id": str(lesson_id),
            "type": TOKEN_TYPE,
            "iat": now,
            "exp": expires_at,
            "jti": str(uuid.uuid4()),
        }
        if conversation_id is not None:
            payload["conversation_id"] = str(conversation_id)

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return token, expires_at

    def validate_readonly(self, token: str) -> HandoffClaims:
        """Valida assinatura e expiração sem consumir o token (reuso permitido)."""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError as exc:
            raise HandoffTokenError("Token de voz expirado", expired=True) from exc
        except jwt.InvalidTokenError as exc:
            raise HandoffTokenError("Token de voz inválido") from exc

        if payload.get("type") != TOKEN_TYPE:
            raise HandoffTokenError("Token de voz inválido")

        try:
            user_id = uuid.UUID(str(payload["sub"]))
            cohort_id = uuid.UUID(str(payload["cohort_id"]))
            lesson_id = uuid.UUID(str(payload["lesson_id"]))
        except (KeyError, ValueError, TypeError) as exc:
            raise HandoffTokenError("Token de voz inválido") from exc

        conversation_id: uuid.UUID | None = None
        raw_conversation_id = payload.get("conversation_id")
        if raw_conversation_id:
            try:
                conversation_id = uuid.UUID(str(raw_conversation_id))
            except (ValueError, TypeError) as exc:
                raise HandoffTokenError("Token de voz inválido") from exc

        exp = payload.get("exp")
        if exp is None:
            raise HandoffTokenError("Token de voz inválido")
        expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)

        return HandoffClaims(
            user_id=user_id,
            cohort_id=cohort_id,
            lesson_id=lesson_id,
            conversation_id=conversation_id,
            jti=str(payload.get("jti") or ""),
            expires_at=expires_at,
        )

    def build_url(self, token: str) -> str:
        base = settings.FRONTEND_BASE_URL.rstrip("/")
        return f"{base}/voz/{token}"
