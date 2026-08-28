"""Cinndi webhook — thin edge, always 200. Path is per organization slug."""

from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.tenancy import Organization
from app.services.cinndi.payload_parser import parse_payload
from app.services.org_config import resolve_org_config
from app.services.whatsapp.debounce import schedule_inbound_processing
from app.services.whatsapp.inbound_service import apply_delivery_ack, persist_inbound

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


def _token_from_request(request: Request) -> str:
    return (
        request.headers.get("X-Webhook-Token")
        or request.headers.get("X-Cinndi-Token")
        or ""
    ).strip()


def _webhook_allowed(request: Request, expected: str) -> bool:
    expected = (expected or "").strip()
    if not expected:
        return True
    got = _token_from_request(request)
    if not got:
        return False
    return hmac.compare_digest(got, expected)


@router.post("/webhooks/cinndi")
async def cinndi_webhook_removed():
    raise HTTPException(
        status.HTTP_410_GONE,
        "Use POST /webhooks/cinndi/{org_slug}",
    )


@router.post("/webhooks/cinndi/{org_slug}")
async def cinndi_org_webhook(org_slug: str, request: Request):
    async with SessionLocal() as db:
        org = await db.scalar(select(Organization).where(Organization.slug == org_slug))
        if org is None or not org.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized")
        config = await resolve_org_config(db, org.id)
        if not _webhook_allowed(request, config.cinndi_webhook_token):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized")

        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001
            return {"status": 200, "detail": "invalid_json"}

        parsed = parse_payload(payload if isinstance(payload, dict) else {})

        try:
            if parsed.is_ack:
                updated = await apply_delivery_ack(db, parsed)
                await db.commit()
                return {"status": 200, "detail": "ack" if updated else "ignored"}

            if parsed.is_inbound_chat:
                result = await persist_inbound(db, parsed)
                await db.commit()
                if result.conversation_id is not None:
                    await schedule_inbound_processing(result.conversation_id)
                return {"status": 200, "detail": result.detail}

        except Exception:
            await db.rollback()
            logger.exception("cinndi webhook processing failed")
            return {"status": 200, "detail": "error"}

    return {"status": 200, "detail": "ignored"}
