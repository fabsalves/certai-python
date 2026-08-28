"""Validate organization API keys against each provider."""
from __future__ import annotations

import httpx

from app.services.org_config import OrgConfig

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
TESTABLE_FIELDS = frozenset({"openai_api_key", "groq_api_key"})


class CredentialTestError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _pick_value(*values: str | None) -> str:
    for value in values:
        if value is not None and value.strip():
            return value.strip()
    return ""


def _provider_error(provider: str, response: httpx.Response) -> str:
    detail = response.text.strip()
    if len(detail) > 180:
        detail = f"{detail[:177]}..."
    if response.status_code in {401, 403}:
        return f"{provider}: chave inválida ou sem permissão."
    if response.status_code == 429:
        return f"{provider}: limite de requisições atingido. Tente novamente em instantes."
    if detail:
        return f"{provider}: erro {response.status_code}: {detail}"
    return f"{provider}: erro {response.status_code}."


async def _get_json(url: str, *, headers: dict[str, str], provider: str) -> dict:
    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        response = await client.get(url)
        if response.is_success:
            return response.json()
        raise CredentialTestError(_provider_error(provider, response))


async def test_openai_api_key(api_key: str) -> str:
    data = await _get_json(
        OPENAI_MODELS_URL,
        headers={"Authorization": f"Bearer {api_key}", "accept": "application/json"},
        provider="OpenAI",
    )
    count = len(data.get("data", []))
    return f"OpenAI OK: {count} modelos disponíveis."


async def test_groq_api_key(api_key: str) -> str:
    data = await _get_json(
        GROQ_MODELS_URL,
        headers={"Authorization": f"Bearer {api_key}", "accept": "application/json"},
        provider="Groq",
    )
    count = len(data.get("data", []))
    return f"Groq OK: {count} modelos disponíveis."


async def run_credential_test(*, field: str, config: OrgConfig, value: str | None = None) -> str:
    if field not in TESTABLE_FIELDS:
        raise CredentialTestError("Campo de teste inválido.")

    if field == "openai_api_key":
        api_key = _pick_value(value, config.openai_api_key)
        if not api_key:
            raise CredentialTestError("Informe a OpenAI API key.")
        return await test_openai_api_key(api_key)

    api_key = _pick_value(value, config.groq_api_key)
    if not api_key:
        raise CredentialTestError("Informe a Groq API key.")
    return await test_groq_api_key(api_key)
