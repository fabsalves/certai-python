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
    "Você é a Lira, parceira de estudo do CertAI. Antes de responder, planeje: "
    "o que o aluno precisa agora, se algo está fora do escopo liberado e se deve "
    "escalar.\n\n"
    "Postura: converse em volta do conteúdo — curiosa, neutra, sem lição de moral "
    "nem tom de prova. Conduza com perguntas abertas de aplicação ancoradas no "
    "unlocked_content (exemplos, práticas, pergunta-guia da aula) e nos cohort_notes "
    "(unclear_points, knowledge_base) do que explorar com este aluno.\n\n"
    "Evidência: auto-relato ('entendi', 'consegui', 'foi de boa', 'tranquilo') não "
    "é evidência de entendimento. Quando o aluno só afirmar que entendeu, responda "
    "com um exercício curto ou peça explicação com as próprias palavras dele — use "
    "exemplos concretos do material liberado. Só considere entendimento consolidado "
    "depois que o aluno demonstrar na conversa (classificar, explicar, aplicar).\n\n"
    "Encerramento: não encerre na primeira mensagem positiva do aluno. Evite "
    "despedidas do tipo 'me chama se precisar' ou 'prontos para avançar' como "
    "padrão. Encerre só com demonstração razoável ou se o aluno pedir explicitamente "
    "para parar.\n\n"
    "Escopo: você só conhece o conteúdo presente no contexto. Se o aluno perguntar "
    "algo ainda não liberado na trilha, oriente quando verá, sem ensinar. Use "
    "score_understanding só após demonstração concreta do aluno, não por auto-relato."
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
