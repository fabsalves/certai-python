"""Low-level Cinndi outbound HTTP calls."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.phone import digits_only
from app.services.cinndi.outbound_message_id import provider_message_id_from_response


class CinndiOutboundError(Exception):
    pass


MAX_ATTEMPTS = 2


def _base_url() -> str:
    return (settings.CINNDI_API_URL or "").rstrip("/")


def _api_key() -> str:
    return settings.CINNDI_API_KEY or ""


def _from_phone() -> str:
    return digits_only(settings.CINNDI_SENDER_PHONE)


def _execute(
    method: str,
    endpoint: str,
    body: dict[str, Any],
    *,
    max_attempts: int = MAX_ATTEMPTS,
    timeout: float = 30.0,
) -> dict[str, Any]:
    if not _base_url() or not _api_key():
        raise CinndiOutboundError("Cinndi API not configured")

    url = f"{_base_url()}/{endpoint.lstrip('/')}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    last_error = "unknown error"

    for attempt in range(1, max(1, max_attempts) + 1):
        try:
            with httpx.Client(timeout=timeout, verify=not settings.CINNDI_INSECURE_SSL) as client:
                response = client.request(method.upper(), url, json=body, headers=headers)
            if response.is_success:
                return {"success": True, "code": response.status_code, "body": response.text}
            last_error = response.text
        except httpx.HTTPError as exc:
            last_error = str(exc)

    raise CinndiOutboundError(last_error)


def send_text_message(*, to_phone: str, body: str) -> str | None:
    from_phone = _from_phone()
    to_digits = digits_only(to_phone)
    if not from_phone or not to_digits:
        raise CinndiOutboundError("invalid from/to phone")

    response = _execute(
        "POST",
        f"enviar-mensagem-texto/{from_phone}/{_api_key()}",
        {"para": to_digits, "mensagem": body},
    )
    return provider_message_id_from_response(response["body"])


def send_template_message(
    *,
    to_phone: str,
    template_name: str,
    body_params: list[str],
    code: str = "pt_BR",
    button_suffix: str | None = None,
) -> str | None:
    """Envia template Cinndi. Para botão URL dinâmico, passe o sufixo em button_suffix."""
    from_phone = _from_phone()
    to_digits = digits_only(to_phone)
    if not from_phone or not to_digits:
        raise CinndiOutboundError("invalid from/to phone")

    payload: dict[str, Any] = {
        "para": to_digits,
        "name": template_name,
        "code": code,
        "header": "",
        "body": list(body_params),
        "buttons": button_suffix or "",
    }

    response = _execute(
        "POST",
        f"enviar-template/{from_phone}/{_api_key()}",
        payload,
    )
    return provider_message_id_from_response(response["body"])


def send_interactive_url_message(
    *,
    to_phone: str,
    body: str,
    url: str,
    button_display: str = "Entrar na aula",
    button_id: str = "open_voice_session",
    header: str | None = None,
    footer: str | None = None,
) -> str | None:
    """Envia mensagem de sessão com botão URL clicável (janela 24h aberta)."""
    from_phone = _from_phone()
    to_digits = digits_only(to_phone)
    if not from_phone or not to_digits:
        raise CinndiOutboundError("invalid from/to phone")
    if not body.strip():
        raise CinndiOutboundError("invalid body")
    if not url.strip():
        raise CinndiOutboundError("invalid url")

    payload: dict[str, Any] = {
        "para": to_digits,
        "type": "button",
        "body": body,
        "buttons": [
            {
                "id": button_id,
                "display": button_display[:20],
                "title": url,
            }
        ],
    }
    if header:
        payload["header"] = header
    if footer:
        payload["footer"] = footer

    response = _execute(
        "POST",
        f"enviar-mensagem-interativa-url/{from_phone}/{_api_key()}",
        payload,
    )
    return provider_message_id_from_response(response["body"])
