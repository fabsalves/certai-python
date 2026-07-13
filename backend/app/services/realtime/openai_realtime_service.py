"""Ephemeral client secrets for browser Realtime WebRTC (OpenAI GA API)."""

from __future__ import annotations

import hashlib
from typing import Any

import httpx

from app.core.config import settings

CLIENT_SECRETS_URL = "https://api.openai.com/v1/realtime/client_secrets"
DEFAULT_MODEL = "gpt-realtime-2"
DEFAULT_VOICE = "coral"
DEFAULT_REASONING_EFFORT = "low"
REASONING_EFFORTS = frozenset({"minimal", "low", "medium", "high", "xhigh"})
DEFAULT_INPUT_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
SILENCE_DURATION_MS = 850


class OpenaiRealtimeError(Exception):
    pass


class OpenaiRealtimeService:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        voice: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise OpenaiRealtimeError("OPENAI_API_KEY is not set")
        self.model = model or settings.OPENAI_REALTIME_MODEL or DEFAULT_MODEL
        self.voice = voice or settings.OPENAI_REALTIME_VOICE or DEFAULT_VOICE

    @staticmethod
    def safety_identifier_for_user(user_id: str) -> str:
        return hashlib.sha256(user_id.encode()).hexdigest()

    async def create_client_secret(
        self,
        *,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        safety_identifier: str | None = None,
    ) -> dict[str, Any]:
        turn_detection = {"type": "server_vad", "silence_duration_ms": SILENCE_DURATION_MS}
        session_config: dict[str, Any] = {
            "type": "realtime",
            "model": self.model,
            "audio": {
                "output": {"voice": self.voice},
                "input": {
                    "turn_detection": turn_detection,
                    "transcription": self._input_transcription_config(),
                },
            },
        }

        reasoning = self._reasoning_config()
        if reasoning:
            session_config["reasoning"] = reasoning

        if tools:
            session_config["tools"] = tools
            session_config["tool_choice"] = "auto"

        if instructions:
            session_config["instructions"] = instructions

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if safety_identifier:
            headers["OpenAI-Safety-Identifier"] = safety_identifier

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                CLIENT_SECRETS_URL,
                headers=headers,
                json={"session": session_config},
            )

        if response.status_code >= 400:
            raise OpenaiRealtimeError(
                f"OpenAI Realtime client_secrets failed: {response.status_code} {response.text}"
            )

        data = response.json()
        value = data.get("value") or (data.get("client_secret") or {}).get("value")
        expires_at = data.get("expires_at") or (data.get("client_secret") or {}).get("expires_at")
        if not value:
            raise OpenaiRealtimeError("OpenAI Realtime client_secrets response missing token value")

        return {
            "value": value,
            "expires_at": expires_at,
            "model": self.model,
            "voice": self.voice,
            "reasoning_effort": reasoning.get("effort") if reasoning else None,
        }

    def _reasoning_model(self) -> bool:
        return "gpt-realtime-2" in self.model

    def _reasoning_config(self) -> dict[str, str] | None:
        if not self._reasoning_model():
            return None
        effort = (settings.OPENAI_REALTIME_REASONING_EFFORT or DEFAULT_REASONING_EFFORT).strip()
        if effort not in REASONING_EFFORTS:
            effort = DEFAULT_REASONING_EFFORT
        return {"effort": effort}

    def _input_transcription_config(self) -> dict[str, str]:
        model = settings.OPENAI_REALTIME_TRANSCRIPTION_MODEL or DEFAULT_INPUT_TRANSCRIPTION_MODEL
        cfg: dict[str, str] = {"model": model}
        lang = (settings.OPENAI_REALTIME_TRANSCRIPTION_LANGUAGE or "").strip()
        if lang:
            cfg["language"] = lang
        return cfg
