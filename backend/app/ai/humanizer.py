"""Humanizer -- final pass.

The engine produces the smart answer. The humanizer rewrites it to sound human.
It is the one that "doesn't slip" on tone, freeing the engine to focus on
intelligence without a thousand constraints. Shared tone lives in persona.LIRA_TONE;
this module adds rewrite-task and text-formatting rules only.

The system prompt is intentionally in pt-BR: it produces the text the user reads.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_openai
from app.ai.persona import LIRA_TONE
from app.core.config import settings
from app.services.usage import UsageScope, record_chat_usage

SYSTEM = (
    "Reescreva a mensagem para aplicar o tom abaixo.\n\n"
    f"{LIRA_TONE}\n\n"
    "Preserve integralmente o conteúdo pedagógico, as perguntas e os pedidos de "
    "prática.\n"
    "Não use markdown, negrito, bullets, listas ou formatação — escreva em prosa "
    "conversacional natural, como uma pessoa falando.\n"
    "Não use travessão. Não adicione emojis que não estavam no texto original.\n"
    "Mude só a forma. Responda apenas com o texto reescrito."
)


async def humanize(
    text: str,
    *,
    db: AsyncSession | None = None,
    scope: UsageScope | None = None,
) -> str:
    """`db` + `scope` are optional so callers without one still work; when they
    are missing the pass simply is not metered -- never attributed to a guess."""
    if not text.strip():
        return text
    client = get_openai()
    resp = await client.chat.completions.create(
        model=settings.HUMANIZER_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text},
        ],
    )
    if db is not None and scope is not None:
        await record_chat_usage(db, scope=scope, operation="humanizer", response=resp)
    return (resp.choices[0].message.content or "").strip() or text
