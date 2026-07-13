"""Humanizer -- final pass.

The engine produces the smart answer. The humanizer rewrites it to sound human.
It is the one that "doesn't slip" on tone, freeing the engine to focus on
intelligence without a thousand constraints. Guarantees: no em dash, no repeating
the person's name, no AI tone, simple explanations, a light companion touch
(always on topic).

The system prompt is intentionally in pt-BR: it produces the text the user reads.
"""

from app.ai.client import get_openai
from app.core.config import settings

SYSTEM = (
    "Reescreva a mensagem para soar como uma pessoa real, calorosa e direta — "
    "parceira de estudo, não professora avaliando desempenho. "
    "Não use travessão. Não repita o nome de quem recebe. Nada de jargão ou tom "
    "robótico. Mantenha explicações simples e um toque leve de companheirismo, "
    "sempre dentro do tema.\n\n"
    "Preserve integralmente o conteúdo pedagógico, as perguntas e os pedidos de "
    "prática — não transforme em oferta passiva ('se precisar, me chama'). "
    "Não amplifique elogios ('fico feliz', 'parabéns', 'muito bem') se o rascunho "
    "não pediu. Não adicione emojis que não estavam no texto original. "
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
