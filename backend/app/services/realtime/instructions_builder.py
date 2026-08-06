"""Assemble Realtime session instructions with cross-channel lesson history."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_openai
from app.ai.context_builder import ContextBuilder
from app.ai.engine import SYSTEM_BASE
from app.ai.persona import LIRA_TONE
from app.core.config import settings
from app.services.conversation_service import lesson_conversation_history

logger = logging.getLogger(__name__)

INSTRUCTIONS_CHAR_LIMIT = 25_000
MAX_HISTORY_TURNS = 20
INSTRUCTIONS_WARN_RATIO = 0.8

VOICE_MODE_BLOCK = """## Modo de conversa
Você está em uma chamada de voz ao vivo. Respostas curtas e naturais para fala.
Não use markdown, listas longas ou formatação. Uma ideia por vez."""

VOICE_CONVERSATION_ORDER_BLOCK = """## Ordem da conversa por voz
A conduta pedagógica acima — conduzir com exercícios e perguntas de aplicação — vale
quando a conversa já está em andamento. Na primeira fala desta chamada, siga o bloco
Abertura mais abaixo; só depois dela entram exercícios e cobrança de resposta."""

PERSUASION_BLOCK = """## Quando o aluno quer sair
Só entre neste fluxo se o aluno, na fala DELE (turno atual ou recente), pedir com clareza
para encerrar, sair, desligar ou pausar. Áudio truncado, “né?”, “hã?”, silêncio ou pedido
de esclarecimento NÃO é pedido para sair — continue a aula.
Nunca invente que o aluno precisa sair ou que há urgência.
Se o pedido for claro: acolha — não encerre de imediato e não chame end_conversation.
Insista pelo menos duas vezes, de forma respeitosa, mostrando o impacto de parar agora:
interromper deixa esta etapa da aula incompleta e prejudica a avaliação do entendimento dele
sobre o tema; ainda falta fechar o assunto com clareza.
Cada tentativa deve ser acolhedora e concreta (falta pouco, pode ser breve, vale um passo a mais).
Nunca seja desrespeitosa, nunca prenda o aluno, nunca repita a mesma insistência em loop infinito.
Se, após as duas tentativas, o aluno insistir de novo com clareza que quer sair, aceite com
naturalidade e assuma a condução do encerramento (ver bloco Encerramento da chamada abaixo)."""

CLOSURE_BLOCK = """## Encerramento da chamada
Só use este bloco depois das insistências E de um novo pedido claro do aluno para sair.
Nunca encerre por suposição. Quando for o caso, feche neste mesmo response do Realtime —
não espere um turno seguinte do aluno.
Obrigatório neste response, nesta ordem de prioridade:
(1) FALE a despedida REAL e COMPLETA em voz — o aluno precisa OUVIR (aviso de encerramento
    + fechamento + até logo). Sem áudio de despedida, não chame a tool.
    Exemplo: "Entendo. Vou encerrar por aqui então. Foi ótimo estudar com você, [nome].
    Até a próxima!"
(2) No MESMO response, depois de gerar essa fala, chame end_conversation — só o sinal
    técnico; o app desliga após o áudio. A tool NUNCA substitui a despedida falada.
Proibido: chamar end_conversation sozinha (sem fala neste response) — isso corta a call
sem despedida. Proibido: só falar a despedida e não chamar a tool — a call fica aberta.
Não use end_conversation só porque o histórico tem despedida antiga de outra sessão."""

LESSON_CLOSURE_BLOCK = """## Encerramento da aula (definitivo)
Distinto do encerramento da chamada acima: este bloco fecha a AULA, não só a sessão de voz.
A call pode ser retomada depois; a aula concluída não volta a aceitar novas interações.
Pedido para sair, desligar ou pausar segue o encerramento da chamada/sessão — não este bloco.

Quando você julgar suficiente o estudo desta aula ATUAL — com base livre no que o aluno
demonstrou na conversa, sem checklist — registre essa demonstração com score_understanding
(se ainda não registrou) e só então encerre a aula neste mesmo turno/response:
fale a despedida final definitiva E chame conclude_lesson juntos — a tool não substitui
a fala; sem a tool a aula não fecha.
Exemplo de despedida: "Acho que fechamos bem o que importava nesta aula. O estudo dela
termina aqui para você. Foi ótimo conversar — até a próxima etapa da trilha!"
conclude_lesson exige micro-score(s) desta aula; sem evidência registrada, não conclua.
Não antecipe a próxima aula — o professor libera o material seguinte."""

# Só no assemble de voz (WhatsApp não tem end_conversation).
LESSON_CLOSURE_CALL_END = """Na voz, no MESMO response da despedida final: chame
conclude_lesson e end_conversation juntos com a fala. O app registra a aula e encerra
a call quando o áudio terminar — o mesmo mecanismo do encerramento parcial da chamada.
Sem end_conversation a call permanece aberta — incorreto."""
RESUMPTION_BLOCK = """## Retomada após despedida recente (só se houver histórico)
Este bloco só vale quando o histórico acima contém mensagens anteriores. Se o histórico
estiver vazio — "(nenhuma mensagem anterior)" — ignore este bloco e siga a Abertura (a).

Se as últimas mensagens forem uma despedida ou encerramento de sessão (não o encerramento
definitivo da aula), a aula ainda está em estudo: não repita a despedida, não trate a
conversa como encerrada de vez e não chame end_conversation nem conclude_lesson só porque
o histórico termina assim. Faça uma saudação nova e retome o ponto pedagógico em andamento
anterior à despedida (o exercício, tema ou pergunta que estavam abertos).
Só reentre em encerramento se o aluno pedir de novo para sair, ou se houver nova
suficiência real demonstrada nesta conversa atual."""

OPENING_BLOCK = """## Abertura
Leia o histórico da conversa desta aula acima antes de falar. Sua abertura depende do que
estiver lá — decida com base no contexto; não assuma retomada por padrão.

(a) Primeira interação — histórico vazio ou "(nenhuma mensagem anterior)":
    Sua primeira fala deve ser completa — no espírito do convite por WhatsApp. Formule com
    suas palavras; o prompt define enquadramento e limites, não roteiro. Percorra estes três
    movimentos num turno de voz:
    (1) Apresentação: diga seu nome (Lira) e apresente-se ao aluno.
        NÃO mencione "avaliação", "avaliar", "acompanhar o que absorveu", "ver o que fixou"
        nem qualquer coisa que sinalize prova ou teste — a avaliação acontece nos bastidores.
    (2) Enquadramento: deixe claro sobre o que vão conversar — cite naturalmente trilha,
        módulo e aula (título/tema do material no contexto). É um bate-papo de estudo sobre
        aquele conteúdo, não uma avaliação declarada ao aluno.
    (3) Convite/gancho: só então convide a conversar sobre o tema — pergunta ou convite curto,
        não interrogatório. Ainda não é hora de puxar exercício ou cobrar resposta certa.
    Não diga "vamos retomar", "de onde paramos" nem trate como continuação.

(b) Retomada — já há mensagens anteriores no histórico:
    Faça uma saudação breve e retome de onde a conversa parou, sem recomeçar do zero.
    Não repita o que já foi dito; avance a partir do último ponto em aberto.
    Se o histórico terminar em despedida de sessão, não se despeça de novo na abertura e
    não chame end_conversation nem conclude_lesson só por isso — retome o estudo."""


def format_history(history: list[dict]) -> str:
    if not history:
        return "(nenhuma mensagem anterior)"
    lines: list[str] = []
    for msg in history:
        role = "Aluno" if msg.get("role") == "user" else "Lira"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(nenhuma mensagem anterior)"


async def _summarize_dropped_turns(dropped: list[dict]) -> str:
    if not dropped:
        return ""
    transcript = format_history(dropped)
    if len(transcript) > 12_000:
        transcript = transcript[-12_000:]

    client = get_openai()
    resp = await client.chat.completions.create(
        model=settings.ENGINE_MODEL,
        max_tokens=512,
        messages=[
            {
                "role": "system",
                "content": (
                    "Resuma em português do Brasil, em poucos parágrafos curtos, "
                    "o que foi discutido nesta conversa de aula. Foque no que o aluno "
                    "já demonstrou entender e nos tópicos em aberto."
                ),
            },
            {"role": "user", "content": transcript},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


class RealtimeInstructionsBuilder:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def build(
        self,
        *,
        cohort_id: uuid.UUID,
        lesson_id: uuid.UUID,
        student_id: uuid.UUID,
        student_first_name: str,
    ) -> str:
        bundle = await ContextBuilder(self._db).build_lesson(
            cohort_id, lesson_id, student_id=student_id
        )
        system_blocks = bundle.to_system_blocks()
        history = await lesson_conversation_history(self._db, cohort_id, student_id, lesson_id)

        return await self._assemble(
            system_blocks=system_blocks,
            history=history,
            student_first_name=student_first_name,
        )

    async def _assemble(
        self,
        *,
        system_blocks: str,
        history: list[dict],
        student_first_name: str,
    ) -> str:
        base_prefix = (
            f"{SYSTEM_BASE}\n\n{VOICE_CONVERSATION_ORDER_BLOCK}\n\n{LIRA_TONE}\n\n"
            f"{system_blocks}\n\n"
            f"{VOICE_MODE_BLOCK}\n\n{PERSUASION_BLOCK}\n\n{CLOSURE_BLOCK}\n\n"
            f"{LESSON_CLOSURE_BLOCK}\n{LESSON_CLOSURE_CALL_END}\n\n"
        )
        student_block = f"## Aluno\nPrimeiro nome: {student_first_name}\n\n"

        def render(hist_block: str, summary: str = "") -> str:
            summary_block = ""
            if summary:
                summary_block = f"## Resumo da conversa anterior\n{summary}\n\n"
            return (
                f"{base_prefix}"
                f"{student_block}"
                f"{summary_block}"
                f"## Histórico da conversa desta aula\n{hist_block}\n\n"
                f"{OPENING_BLOCK}\n\n"
                f"{RESUMPTION_BLOCK}"
            )

        def finish(text: str) -> str:
            warn_at = int(INSTRUCTIONS_CHAR_LIMIT * INSTRUCTIONS_WARN_RATIO)
            n = len(text)
            if n > warn_at:
                logger.warning(
                    "Realtime instructions size %s chars exceeds 80%% of limit %s",
                    n,
                    INSTRUCTIONS_CHAR_LIMIT,
                )
            return text

        full = render(format_history(history))
        if len(full) <= INSTRUCTIONS_CHAR_LIMIT:
            return finish(full)

        recent = history[-MAX_HISTORY_TURNS:]
        dropped = history[:-MAX_HISTORY_TURNS]
        truncated = render(format_history(recent))
        if len(truncated) <= INSTRUCTIONS_CHAR_LIMIT:
            return finish(truncated)

        summary = await _summarize_dropped_turns(dropped)
        with_summary = render(format_history(recent), summary=summary)
        if len(with_summary) <= INSTRUCTIONS_CHAR_LIMIT:
            return finish(with_summary)

        return finish(truncated)
