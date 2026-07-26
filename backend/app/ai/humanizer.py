"""Humanizer -- final pass.

The engine produces the smart answer. The humanizer rewrites it to sound human.
It is the one that "doesn't slip" on tone, freeing the engine to focus on
intelligence without a thousand constraints. Shared tone lives in persona.LIRA_TONE;
this module adds rewrite-task and text-formatting rules only.

The system prompt is intentionally in pt-BR: it produces the text the user reads.
"""

from app.ai.client import get_openai
from app.ai.persona import LIRA_TONE
from app.core.config import settings

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


async def humanize(text: str) -> str:
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
    return (resp.choices[0].message.content or "").strip() or text
