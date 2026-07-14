"""Regression checks for dispatch voice invite (template + JWT button).

Ensures the VoiceLinkService refactor does not change the initial invite path.
Does NOT cover request_session_link (on-demand tool).
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, ".")

from app.core.config import settings
from app.models.conversation import Author, Conversation, ConversationChannel, ConversationScope
from app.models.track import Lesson
from app.models.user import Role, User
from app.services.realtime.handoff_token_service import HandoffTokenService
from app.services.realtime.voice_link_service import VoiceLinkService
from app.services.whatsapp import dispatch_service


def test_generate_token_delegates_to_handoff_service_with_same_claims() -> None:
    user_id = uuid.uuid4()
    cohort_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    fixed_expires = datetime(2026, 7, 16, tzinfo=timezone.utc)

    handoff = MagicMock(spec=HandoffTokenService)
    handoff.generate.return_value = ("jwt-token-abc", fixed_expires)
    handoff.build_url.return_value = "https://app.test/voz/jwt-token-abc"

    link = VoiceLinkService(handoff_service=handoff).generate_token(
        user_id=user_id,
        cohort_id=cohort_id,
        lesson_id=lesson_id,
        conversation_id=conversation_id,
    )

    handoff.generate.assert_called_once_with(
        user_id=user_id,
        cohort_id=cohort_id,
        lesson_id=lesson_id,
        conversation_id=conversation_id,
    )
    handoff.build_url.assert_called_once_with("jwt-token-abc")
    assert link.token == "jwt-token-abc"
    assert link.url == "https://app.test/voz/jwt-token-abc"
    assert link.expires_at == fixed_expires


async def _test_dispatch_voice_invite_sends_template_with_jwt_button() -> None:
    cohort_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    student_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    fixed_token = "fixed-handoff-jwt-for-regression"

    cohort = MagicMock()
    cohort.id = cohort_id
    cohort.track_id = uuid.uuid4()

    lesson = Lesson(id=lesson_id, title="Aula de Teste", module_id=uuid.uuid4())

    student = User(
        id=student_id,
        email="aluno@teste.local",
        hashed_password="x",
        name="Maria Silva",
        role=Role.STUDENT,
        is_active=True,
        whatsapp="5511999999999",
    )

    conversation = Conversation(
        id=conversation_id,
        cohort_id=cohort_id,
        user_id=student_id,
        lesson_id=lesson_id,
        scope=ConversationScope.STUDENT_LESSON,
        channel=ConversationChannel.WHATSAPP,
    )

    db = MagicMock()
    db.get = AsyncMock(side_effect=lambda _model, _id: {
        cohort_id: cohort,
        lesson_id: lesson,
    }.get(_id))
    db.scalar = AsyncMock(return_value=None)
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=lambda: [student])))
    )
    db.commit = AsyncMock()

    captured_template: dict = {}

    def fake_send_template_message(**kwargs):
        captured_template.update(kwargs)
        return "provider-msg-id"

    with (
        patch.object(settings, "WHATSAPP_INVITE_USE_VOICE_TEMPLATE", True),
        patch.object(settings, "WHATSAPP_INVITE_VOICE_TEMPLATE", "certai_convite_aula_voz_v2"),
        patch.object(settings, "WHATSAPP_TEMPLATE_LANG", "pt_BR"),
        patch.object(settings, "ASSISTANT_NAME", "Lira"),
        patch(
            "app.services.whatsapp.dispatch_service.get_or_create_conversation",
            new=AsyncMock(return_value=conversation),
        ),
        patch(
            "app.services.whatsapp.dispatch_service._already_dispatched",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.services.whatsapp.dispatch_service._voice_link_service.generate_token",
            return_value=MagicMock(token=fixed_token, url=f"https://app.test/voz/{fixed_token}"),
        ) as generate_token_mock,
        patch(
            "app.services.whatsapp.dispatch_service.send_template_message",
            side_effect=fake_send_template_message,
        ),
        patch(
            "app.services.whatsapp.dispatch_service.record_message",
            new=AsyncMock(),
        ) as record_message_mock,
    ):
        result = await dispatch_service.dispatch_lesson_invites(db, cohort_id, lesson_id)

    assert result["status"] == "planned"
    assert result["sent"] == 1
    assert result["voice_template"] is True

    generate_token_mock.assert_called_once_with(
        user_id=student_id,
        cohort_id=cohort_id,
        lesson_id=lesson_id,
        conversation_id=conversation_id,
    )

    assert captured_template["to_phone"] == "5511999999999"
    assert captured_template["template_name"] == "certai_convite_aula_voz_v2"
    assert captured_template["body_params"] == ["Maria", "Aula de Teste", "", "Lira"]
    assert captured_template["code"] == "pt_BR"
    assert captured_template["button_suffix"] == fixed_token

    record_message_mock.assert_awaited_once()
    record_args = record_message_mock.await_args.args
    assert record_args[2] == Author.AGENT
    assert "Prefere falar comigo ao vivo" in record_args[3]


async def _test_dispatch_skips_when_already_dispatched() -> None:
    cohort_id = uuid.uuid4()
    lesson_id = uuid.uuid4()

    cohort = MagicMock()
    cohort.id = cohort_id
    cohort.track_id = uuid.uuid4()
    lesson = Lesson(id=lesson_id, title="Aula", module_id=uuid.uuid4())

    db = MagicMock()
    db.get = AsyncMock(side_effect=lambda _model, _id: {cohort_id: cohort, lesson_id: lesson}.get(_id))
    db.scalar = AsyncMock(return_value=None)
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=lambda: [])))
    )
    db.commit = AsyncMock()

    with patch.object(settings, "WHATSAPP_INVITE_USE_VOICE_TEMPLATE", True):
        result = await dispatch_service.dispatch_lesson_invites(db, cohort_id, lesson_id)

    assert result["sent"] == 0
    assert result["skipped"] == 0


def main() -> None:
    test_generate_token_delegates_to_handoff_service_with_same_claims()
    asyncio.run(_test_dispatch_voice_invite_sends_template_with_jwt_button())
    asyncio.run(_test_dispatch_skips_when_already_dispatched())
    print("verify_dispatch_voice_invite: OK")


if __name__ == "__main__":
    main()
