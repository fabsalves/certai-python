"""Resolve per-organization configuration: DB (encrypted secrets) with ENV fallback."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, fields

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings as app_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.masking import mask_api_key
from app.models import OrgSettings

CACHE_TTL_SECONDS = 60
_cache: dict[uuid.UUID, tuple[float, "OrgConfig"]] = {}

SECRET_FIELDS = (
    "openai_api_key",
    "groq_api_key",
    "cinndi_api_key",
    "cinndi_webhook_token",
)

PLAIN_FIELDS = (
    "engine_model",
    "humanizer_model",
    "evaluator_model",
    "groq_transcribe_model",
    "openai_realtime_model",
    "openai_realtime_voice",
    "cinndi_api_url",
    "cinndi_sender_phone",
    "whatsapp_invite_template",
    "whatsapp_invite_voice_template",
    "whatsapp_invite_use_voice_template",
    "whatsapp_template_lang",
)


@dataclass(frozen=True)
class OrgConfig:
    openai_api_key: str = ""
    groq_api_key: str = ""
    cinndi_api_key: str = ""
    cinndi_webhook_token: str = ""
    engine_model: str = "gpt-4o"
    humanizer_model: str = "gpt-4o-mini"
    evaluator_model: str = "gpt-4o"
    groq_transcribe_model: str = "whisper-large-v3"
    openai_realtime_model: str = "gpt-realtime-2"
    openai_realtime_voice: str = "coral"
    cinndi_api_url: str = ""
    cinndi_sender_phone: str = ""
    whatsapp_invite_template: str = "certai_convite_aula"
    whatsapp_invite_voice_template: str = "certai_convite_aula_voz_v2"
    whatsapp_invite_use_voice_template: bool = False
    whatsapp_template_lang: str = "pt_BR"
    assistant_name: str = "Lira"

    @classmethod
    def from_settings(cls, cfg: Settings) -> "OrgConfig":
        return cls(
            openai_api_key=cfg.OPENAI_API_KEY,
            groq_api_key=cfg.GROQ_API_KEY,
            cinndi_api_key=cfg.CINNDI_API_KEY,
            cinndi_webhook_token=cfg.CINNDI_WEBHOOK_TOKEN,
            engine_model=cfg.ENGINE_MODEL,
            humanizer_model=cfg.HUMANIZER_MODEL,
            evaluator_model=cfg.EVALUATOR_MODEL,
            groq_transcribe_model=cfg.GROQ_TRANSCRIBE_MODEL,
            openai_realtime_model=cfg.OPENAI_REALTIME_MODEL,
            openai_realtime_voice=cfg.OPENAI_REALTIME_VOICE,
            cinndi_api_url=cfg.CINNDI_API_URL,
            cinndi_sender_phone=cfg.CINNDI_SENDER_PHONE,
            whatsapp_invite_template=cfg.WHATSAPP_INVITE_TEMPLATE,
            whatsapp_invite_voice_template=cfg.WHATSAPP_INVITE_VOICE_TEMPLATE,
            whatsapp_invite_use_voice_template=cfg.WHATSAPP_INVITE_USE_VOICE_TEMPLATE,
            whatsapp_template_lang=cfg.WHATSAPP_TEMPLATE_LANG,
            assistant_name=cfg.ASSISTANT_NAME,
        )

    def configured_secrets(self) -> dict[str, bool]:
        return {field: bool(getattr(self, field)) for field in SECRET_FIELDS}

    def masked_secrets(self) -> dict[str, str]:
        return {
            field: mask_api_key(getattr(self, field)) if getattr(self, field) else ""
            for field in SECRET_FIELDS
        }

    def public_settings(self, org_row: OrgSettings | None = None) -> dict:
        data = {field: getattr(self, field) for field in PLAIN_FIELDS}
        data["assistant_name"] = self.assistant_name
        data["available"] = self.configured_secrets()
        if org_row is None:
            data["configured"] = data["available"]
            data["masked_secrets"] = self.masked_secrets()
            return data

        secrets = org_row.secrets or {}
        data["configured"] = {field: bool(secrets.get(field)) for field in SECRET_FIELDS}
        masked: dict[str, str] = {}
        for field in SECRET_FIELDS:
            token = secrets.get(field)
            if not token:
                masked[field] = ""
                continue
            try:
                masked[field] = mask_api_key(decrypt_secret(token))
            except ValueError:
                masked[field] = ""
        data["masked_secrets"] = masked
        return data


def invalidate_org_config_cache(org_id: uuid.UUID) -> None:
    _cache.pop(org_id, None)


async def get_or_create_org_settings(db: AsyncSession, org_id: uuid.UUID) -> OrgSettings:
    row = await db.scalar(select(OrgSettings).where(OrgSettings.organization_id == org_id))
    if row is None:
        row = OrgSettings(organization_id=org_id, settings={}, secrets={})
        db.add(row)
        await db.flush()
    return row


async def resolve_org_config(db: AsyncSession, org_id: uuid.UUID | None) -> OrgConfig:
    if org_id is None:
        return OrgConfig.from_settings(app_settings)

    now = time.monotonic()
    cached = _cache.get(org_id)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    base = OrgConfig.from_settings(app_settings)
    row = await db.scalar(select(OrgSettings).where(OrgSettings.organization_id == org_id))
    if row is None:
        _cache[org_id] = (now, base)
        return base

    merged = _merge_row(base, row)
    _cache[org_id] = (now, merged)
    return merged


def _merge_row(base: OrgConfig, row: OrgSettings) -> OrgConfig:
    values = {field.name: getattr(base, field.name) for field in fields(OrgConfig)}

    for key in PLAIN_FIELDS:
        if key not in (row.settings or {}):
            continue
        stored = row.settings[key]
        if stored == getattr(base, key):
            continue
        values[key] = stored

    for key in SECRET_FIELDS:
        token = (row.secrets or {}).get(key)
        if not token:
            continue
        try:
            values[key] = decrypt_secret(token)
        except ValueError:
            continue

    return OrgConfig(**values)


async def update_org_settings(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    plain_updates: dict | None = None,
    secret_updates: dict | None = None,
    clear_secrets: set[str] | None = None,
) -> OrgConfig:
    row = await get_or_create_org_settings(db, org_id)
    env = OrgConfig.from_settings(app_settings)

    if plain_updates:
        merged = dict(row.settings or {})
        for key, value in plain_updates.items():
            if key not in PLAIN_FIELDS:
                continue
            if value == getattr(env, key):
                merged.pop(key, None)
            else:
                merged[key] = value
        row.settings = merged

    secrets = dict(row.secrets or {})
    if clear_secrets:
        for key in clear_secrets:
            if key in SECRET_FIELDS:
                secrets.pop(key, None)

    if secret_updates:
        for key, plain in secret_updates.items():
            if key not in SECRET_FIELDS or not str(plain).strip():
                continue
            secrets[key] = encrypt_secret(str(plain).strip())

    row.secrets = secrets
    invalidate_org_config_cache(org_id)
    await db.flush()
    return await resolve_org_config(db, org_id)
