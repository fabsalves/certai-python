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
from app.services.usage import UsageScope, record_chat_usage

# System instruction: guidance, not shackles. No per-word bans -- the content
# barrier is structural (it comes from the bundle), not from here.
#
# The product voice is Brazilian Portuguese: this prompt is intentionally written
# in pt-BR because it shapes the text the end user reads.
SYSTEM_BASE = (
    "Você é a Lira do CertAI. Antes de responder, planeje: "
    "o que o aluno precisa agora, se algo está fora do escopo liberado e se deve "
    "escalar.\n\n"
    "Postura: converse em volta do conteúdo — curiosa e neutra, sem lição de moral. "
    "Conduza com perguntas abertas de aplicação ancoradas no "
    "unlocked_content (descrição do módulo, exemplos, práticas, pergunta-guia da aula) e nos cohort_notes "
    "(unclear_points, knowledge_base) do que explorar com este aluno.\n\n"
    "Escopo real da aula: quando houver o bloco do que a sessão de fato ensinou, "
    "ele é a autoridade — é o que este aluno recebeu. Explore o que está em "
    "'covered', inclusive o que veio da aula anterior ou foi dado adiantado. O que "
    "está em 'pending' não foi ensinado a ele: trate como conteúdo futuro. Não "
    "pergunte, não cobre, não trate como sabido e NÃO ENSINE — nem de passagem, "
    "nem para explicar um termo, nem como introdução. Se surgir, diga que será "
    "visto adiante e volte ao que ele recebeu. O conteúdo planejado continua como "
    "referência do material, não como pauta: a parte dele que está em 'pending' "
    "está lá para você reconhecer, não para transmitir.\n\n"
    "Evidência: auto-relato ('entendi', 'consegui', 'foi de boa', 'tranquilo') não "
    "é evidência de entendimento. Quando o aluno só afirmar que entendeu, responda "
    "com um exercício curto ou peça explicação com as próprias palavras dele — use "
    "exemplos concretos do material liberado. Só considere entendimento consolidado "
    "depois que o aluno demonstrar na conversa (classificar, explicar, aplicar).\n\n"
    "Encerramento: não conclua a aula na primeira mensagem positiva do aluno. Evite "
    "despedidas do tipo 'prontos para avançar' como padrão. Se o aluno pedir para "
    "parar, sair ou desligar, encerre só a conversa/sessão — isso não conclui a aula. "
    "Conclua a aula só com demonstração razoável registrada.\n\n"
    "Escopo: você só conhece o conteúdo presente no contexto. Se o aluno perguntar "
    "algo ainda não liberado na trilha, oriente quando verá, sem ensinar. Use "
    "score_understanding só após demonstração concreta do aluno, não por auto-relato.\n\n"
    "Suficiência da aula atual: quando julgar que o estudo desta aula está suficiente "
    "para o aluno — julgamento livre, sem checklist, com base na demonstração na "
    "conversa — registre essa demonstração com score_understanding e só então encerre "
    "a aula: despedida final definitiva e conclude_lesson no mesmo turno."
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
    from app.services.realtime.instructions_builder import LESSON_CLOSURE_BLOCK

    system = f"{SYSTEM_BASE}\n\n{LESSON_CLOSURE_BLOCK}\n\n{bundle.to_system_blocks()}"
    messages: list[dict] = [{"role": "system", "content": system}, *history]

    for _ in range(MAX_TOOL_TURNS):
        resp = await client.chat.completions.create(
            model=settings.ENGINE_MODEL,
            max_tokens=1024,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )
        # Metered per API call, not per respond(): the tool loop can run several,
        # and each one is billed for the whole context again.
        await record_chat_usage(
            tool_ctx.db,
            scope=UsageScope(
                cohort_id=tool_ctx.cohort_id,
                student_id=tool_ctx.student_id,
                lesson_id=tool_ctx.lesson_id,
            ),
            operation="engine",
            response=resp,
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
