"""Unified voice session link generation and WhatsApp delivery."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools import ToolContext
from app.core.config import settings
from app.models.conversation import Author, ConversationChannel, MessageSource
from app.models.user import User
from app.services.cinndi.outbound import CinndiOutboundError, send_interactive_url_message
from app.services.conversation_service import get_or_create_conversation, record_message
from app.services.realtime.handoff_token_service import HandoffTokenService
from app.services.whatsapp.window_service import is_session_window_open

logger = logging.getLogger(__name__)

VOICE_LINK_BUTTON_DISPLAY = "Entrar na aula"
VOICE_LINK_BUTTON_ID = "open_voice_session"


class WhatsAppWindowClosed(Exception):
    """Raised when the Meta 24h session window is closed for the student."""


@dataclass(frozen=True)
class VoiceLinkToken:
    token: str
    url: str
    expires_at: datetime


def _first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else full_name


def render_session_link_body(*, first_name: str, url: str) -> str:
    """Corpo persistido no DB — inclui URL para histórico."""
    return (
        f"Oi {first_name}! Aqui está seu link atualizado para continuar a aula de voz:\n"
        f"{url}"
    )


def render_session_link_message(*, first_name: str) -> str:
    """Corpo enviado no WhatsApp — o link vai no botão, não no texto."""
    return (
        f"Oi {first_name}! Aqui está seu link atualizado para continuar a aula de voz."
    )


_LINK_DELIVERED_VOICE = "Link da sessão de voz enviado no WhatsApp do aluno."

_LINK_DELIVERED_WHATSAPP = (
    "Botão com link de voz já entregue nesta mesma conversa do WhatsApp. "
    "NÃO envie outra mensagem confirmando o envio — o botão já é a resposta completa. "
    "Só continue se houver algo pedagógico a acrescentar; caso contrário, não responda."
)


class VoiceLinkService:
    def __init__(self, handoff_service: HandoffTokenService | None = None) -> None:
        self._handoff = handoff_service or HandoffTokenService()

    def generate_token(
        self,
        *,
        user_id: uuid.UUID,
        cohort_id: uuid.UUID,
        lesson_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> VoiceLinkToken:
        token, expires_at = self._handoff.generate(
            user_id=user_id,
            cohort_id=cohort_id,
            lesson_id=lesson_id,
            conversation_id=conversation_id,
        )
        return VoiceLinkToken(
            token=token,
            url=self._handoff.build_url(token),
            expires_at=expires_at,
        )

    async def deliver_via_whatsapp(
        self,
        db: AsyncSession,
        student: User,
        url: str,
        *,
        cohort_id: uuid.UUID,
        lesson_id: uuid.UUID,
        proactive: bool = False,
    ) -> None:
        del proactive  # reserved for Phase 3 proactive delivery hooks

        if not student.whatsapp:
            raise ValueError("student has no whatsapp number")

        if not await is_session_window_open(db, student.id):
            raise WhatsAppWindowClosed()

        conversation = await get_or_create_conversation(
            db,
            cohort_id,
            student.id,
            lesson_id,
            channel=ConversationChannel.WHATSAPP,
        )
        body = render_session_link_body(first_name=_first_name(student.name), url=url)
        message = render_session_link_message(first_name=_first_name(student.name))

        try:
            provider_id = await asyncio.to_thread(
                send_interactive_url_message,
                to_phone=student.whatsapp,
                body=message,
                url=url,
                button_display=VOICE_LINK_BUTTON_DISPLAY,
                button_id=VOICE_LINK_BUTTON_ID,
            )
        except CinndiOutboundError as exc:
            logger.warning(
                "voice link whatsapp delivery failed student=%s lesson=%s: %s",
                student.id,
                lesson_id,
                exc,
            )
            raise

        await record_message(
            db,
            conversation,
            Author.AGENT,
            body,
            provider_message_id=provider_id,
            delivery_status="sent",
            source=MessageSource.WHATSAPP_TEXT,
        )

    async def generate_and_deliver(self, ctx: ToolContext) -> str:
        if ctx.student_id is None or ctx.lesson_id is None:
            return "Não foi possível enviar o link: contexto de aluno ou aula ausente."

        student = await ctx.db.get(User, ctx.student_id)
        if student is None:
            return "Não foi possível enviar o link: aluno não encontrado."
        if not student.whatsapp:
            return "Não foi possível enviar o link: aluno sem número de WhatsApp cadastrado."

        whatsapp_conversation = await get_or_create_conversation(
            ctx.db,
            ctx.cohort_id,
            ctx.student_id,
            ctx.lesson_id,
            channel=ConversationChannel.WHATSAPP,
        )
        link = self.generate_token(
            user_id=ctx.student_id,
            cohort_id=ctx.cohort_id,
            lesson_id=ctx.lesson_id,
            conversation_id=whatsapp_conversation.id,
        )

        try:
            await self.deliver_via_whatsapp(
                ctx.db,
                student,
                link.url,
                cohort_id=ctx.cohort_id,
                lesson_id=ctx.lesson_id,
            )
        except WhatsAppWindowClosed:
            return (
                "Não foi possível enviar o link agora: a janela de mensagens do WhatsApp "
                "está fechada (sem mensagem do aluno nas últimas 24h). Informe gentilmente."
            )
        except (CinndiOutboundError, ValueError) as exc:
            logger.warning(
                "request_session_link failed student=%s lesson=%s: %s",
                ctx.student_id,
                ctx.lesson_id,
                exc,
            )
            return (
                "Não foi possível enviar o link agora por falha no envio. "
                "Informe gentilmente e sugira tentar novamente."
            )

        if ctx.channel == ConversationChannel.WHATSAPP:
            return _LINK_DELIVERED_WHATSAPP
        return _LINK_DELIVERED_VOICE
