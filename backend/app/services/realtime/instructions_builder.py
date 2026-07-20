"""Assemble Realtime session instructions with cross-channel lesson history."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_openai
from app.ai.context_builder import ContextBuilder
from app.ai.engine import SYSTEM_BASE
from app.ai.persona import LIRA_TONE
from app.core.config import settings
from app.services.conversation_service import lesson_conversation_history

INSTRUCTIONS_CHAR_LIMIT = 25_000
MAX_HISTORY_TURNS = 20

VOICE_MODE_BLOCK = """## Modo de conversa
Você está em uma chamada de voz ao vivo. Respostas curtas e naturais para fala.
Não use markdown, listas longas ou formatação. Uma ideia por vez."""

PERSUASION_BLOCK = """## Quando o aluno quer sair
Se o aluno sinalizar que quer encerrar, sair ou desligar, acolha — não encerre de imediato e
não chame end_conversation.
Insista pelo menos duas vezes, de forma respeitosa, mostrando o impacto de parar agora:
interromper deixa esta etapa da aula incompleta e prejudica a avaliação do entendimento dele
sobre o tema; ainda falta fechar o assunto com clareza.
Cada tentativa deve ser acolhedora e concreta (falta pouco, pode ser breve, vale um passo a mais).
Nunca seja desrespeitosa, nunca prenda o aluno, nunca repita a mesma insistência em loop infinito.
Se, após as duas tentativas, o aluno insistir que quer sair de verdade, aceite com naturalidade
e assuma a condução do encerramento (ver bloco Encerramento da chamada abaixo)."""

CLOSURE_BLOCK = """## Encerramento da chamada
Separe o ato conversacional do sinal técnico — ordem obrigatória em três movimentos:
(a) Insistência: pelo menos duas tentativas de convidar a continuar (bloco anterior).
(b) Fechamento em voz: se o aluno mantiver a decisão de sair, avise-o com naturalidade que
    vai encerrar, conduza o fechamento do assunto e diga a despedida REAL e COMPLETA em voz
    — um turno de fala normal, só conversa, sem chamar end_conversation neste turno.
    Exemplo de despedida: "Entendo. Vou encerrar por aqui então. Foi ótimo estudar com você,
    [nome]. Até a próxima!"
(c) Sinal técnico: somente no movimento SEGUINTE, depois de já ter falado a despedida em voz,
    chame end_conversation — é só o marcador de fim da call, nunca o veículo da despedida.
Anunciar que vai encerrar, preparar o encerramento ou falar sobre a tool NÃO substitui a
despedida falada. end_conversation sem despedida prévia em voz é incorreto."""

LESSON_CLOSURE_BLOCK = """## Encerramento da aula (definitivo)
Distinto do encerramento da chamada acima: este bloco fecha a AULA, não só a sessão de voz.
A call pode ser retomada depois; a aula concluída não volta a aceitar novas interações.

Quando você julgar suficiente o estudo desta aula ATUAL — com base livre no que o aluno
demonstrou na conversa, sem checklist, sem reler micro-scores — conduza o encerramento em
dois movimentos obrigatórios:
(a) Despedida final em conversa: num turno completo, comunique que o estudo desta aula
    terminou para o aluno, feche o assunto pedagógico com naturalidade, agradeça e despeça-se
    de verdade. Não chame conclude_lesson neste turno.
    Exemplo: "Acho que fechamos bem o que importava nesta aula. O estudo dela termina aqui
    para você. Foi ótimo conversar — até a próxima etapa da trilha!"
(b) Registro: somente no movimento SEGUINTE, depois da despedida já falada ao aluno,
    chame conclude_lesson — é só o registro de conclusão, nunca o veículo da despedida.

Anunciar que vai concluir, preparar o encerramento ou falar sobre a tool NÃO substitui a
despedida falada. conclude_lesson sem despedida prévia na conversa é incorreto.
Não crie nem antecipe a próxima aula — o professor libera o material seguinte."""

RESUMPTION_BLOCK = """## Retomada após despedida recente (só se houver histórico)
Este bloco só vale quando o histórico acima contém mensagens anteriores. Se o histórico
estiver vazio — "(nenhuma mensagem anterior)" — ignore este bloco e siga a Abertura (a).

Se as últimas mensagens forem uma despedida ou encerramento de sessão (não o encerramento
definitivo da aula), não repita a despedida nem trate a conversa como encerrada de vez.
Faça uma saudação nova e retome o ponto pedagógico em andamento anterior à despedida
(o exercício, tema ou pergunta que estavam abertos)."""

OPENING_BLOCK = """## Abertura
Leia o histórico da conversa desta aula acima antes de falar. Sua abertura depende do que
estiver lá — decida com base no contexto; não assuma retomada por padrão.

(a) Primeira interação — histórico vazio ou "(nenhuma mensagem anterior)":
    Na primeira fala desta chamada, este caso tem precedência sobre a conduta pedagógica
    geral — inclusive "conduza com perguntas de aplicação" e uso da pergunta-guia do material.
    Ainda não aplique exercícios nem cobrança de resposta; primeiro complete apresentação,
    enquadramento e gancho.
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
    Não repita o que já foi dito; avance a partir do último ponto em aberto."""


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
        bundle = await ContextBuilder(self._db).build_lesson(cohort_id, lesson_id)
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
            f"{SYSTEM_BASE}\n\n{LIRA_TONE}\n\n{system_blocks}\n\n"
            f"{VOICE_MODE_BLOCK}\n\n{PERSUASION_BLOCK}\n\n{CLOSURE_BLOCK}\n\n"
            f"{LESSON_CLOSURE_BLOCK}\n\n"
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

        full = render(format_history(history))
        if len(full) <= INSTRUCTIONS_CHAR_LIMIT:
            return full

        recent = history[-MAX_HISTORY_TURNS:]
        dropped = history[:-MAX_HISTORY_TURNS]
        truncated = render(format_history(recent))
        if len(truncated) <= INSTRUCTIONS_CHAR_LIMIT:
            return truncated

        summary = await _summarize_dropped_turns(dropped)
        with_summary = render(format_history(recent), summary=summary)
        if len(with_summary) <= INSTRUCTIONS_CHAR_LIMIT:
            return with_summary

        return truncated
