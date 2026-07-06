"""Cinndi webhook — thin edge, always 200."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.cinndi.payload_parser import parse_payload
from app.services.whatsapp.debounce import schedule_inbound_processing
from app.services.whatsapp.inbound_service import apply_delivery_ack, persist_inbound

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


def _webhook_allowed(request: Request) -> bool:
    expected = (settings.CINNDI_WEBHOOK_TOKEN or "").strip()
    if not expected:
        return True
    got = (
        request.headers.get("X-Webhook-Token")
        or request.headers.get("X-Cinndi-Token")
        or ""
    ).strip()
    if not got:
        return False
    return got == expected


@router.post("/webhooks/cinndi")
async def cinndi_webhook(request: Request):
    if not _webhook_allowed(request):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized")

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return {"status": 200, "detail": "invalid_json"}

    parsed = parse_payload(payload if isinstance(payload, dict) else {})

    async with SessionLocal() as db:
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
