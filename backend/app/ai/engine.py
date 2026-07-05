"""AI engine -- single integration.

A single, scope-agnostic component. It does not know whether it is at the track,
module or lesson level: it receives the assembled context plus the conversation and
decides everything (including when to call tools and when to escalate scope). The
"three engines" from the diagram are this same engine with different context bundles.

Few textual rules, lots of context. Per-step planning is done by the AI itself on
the first turn (minimal system instruction below).
"""

import json

from app.ai.client import get_openai
from app.ai.context_builder import ContextBundle
from app.ai.tools import TOOL_SCHEMAS, ToolContext, dispatch
from app.core.config import settings

# System instruction: guidance, not shackles. No per-word bans -- the content
# barrier is structural (it comes from the bundle), not from here.
#
# The product voice is Brazilian Portuguese: this prompt is intentionally written
# in pt-BR because it shapes the text the end user reads.
SYSTEM_BASE = (
    "Você é a Lira, agente de aprendizado do CertAI. Antes de responder, planeje: "
    "decida o que o aluno precisa agora, se algo está fora do escopo liberado e se "
    "deve escalar. Você só conhece o conteúdo presente no contexto; se o aluno "
    "perguntar algo que ainda não foi liberado na trilha, oriente sobre quando "
    "verá, sem ensinar o conteúdo. Pontue o entendimento quando houver sinal claro. "
    "Seja inteligente e bem contextualizada."
)

MAX_TOOL_TURNS = 6


async def respond(
    bundle: ContextBundle,
    history: list[dict],
    tool_ctx: ToolContext,
) -> str:
    """Run the reasoning + tools loop and return the AI's raw answer.

    `history` is the list of messages in API format ({role, content}).
    Humanization is a separate pass (see humanizer.py).
    """
    client = get_openai()
    system = f"{SYSTEM_BASE}\n\n{bundle.to_system_blocks()}"
    messages: list[dict] = [{"role": "system", "content": system}, *history]

    for _ in range(MAX_TOOL_TURNS):
        resp = await client.chat.completions.create(
            model=settings.ENGINE_MODEL,
            max_tokens=1024,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )
        message = resp.choices[0].message

        if message.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
            )
            for tc in message.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                out = await dispatch(tc.function.name, args, tool_ctx)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": out,
                    }
                )
            continue

        text = (message.content or "").strip()
        if text:
            return text

    return "Não consegui concluir o raciocínio agora. Pode reformular?"
