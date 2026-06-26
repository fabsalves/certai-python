"""AI engine -- single integration.

A single, scope-agnostic component. It does not know whether it is at the track,
module or lesson level: it receives the assembled context plus the conversation and
decides everything (including when to call tools and when to escalate scope). The
"three engines" from the diagram are this same engine with different context bundles.

Few textual rules, lots of context. Per-step planning is done by the AI itself on
the first turn (minimal system instruction below).
"""

from app.ai.client import get_anthropic
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
    client = get_anthropic()
    system = f"{SYSTEM_BASE}\n\n{bundle.to_system_blocks()}"
    messages = list(history)

    for _ in range(MAX_TOOL_TURNS):
        resp = await client.messages.create(
            model=settings.ENGINE_MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    out = await dispatch(block.name, block.input, tool_ctx)
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": out,
                        }
                    )
            messages.append({"role": "user", "content": results})
            continue

        return "".join(b.text for b in resp.content if b.type == "text")

    return "Não consegui concluir o raciocínio agora. Pode reformular?"
