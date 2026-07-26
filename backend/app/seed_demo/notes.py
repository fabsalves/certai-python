"""Hand-written professor lesson notes for the demo cohort (no AI)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LessonNoteSeed:
    lesson_key: str
    summary: str
    unclear_points: str
    professor_transcript: str


# Keys match profiles.LESSON_KEYS / texts lesson keys.
LESSON_NOTES: list[LessonNoteSeed] = [
    LessonNoteSeed(
        lesson_key="leitura_critica",
        summary=(
            "Separação fato vs interpretação com o e-mail «Não vou aprovar isso agora.» "
            "Turma usou a pergunta-guia e trouxe trechos do trabalho."
        ),
        unclear_points=(
            "Alguns ainda tratam o «clima» da mensagem como se estivesse escrito. "
            "Pedi para apontar a frase antes de opinar."
        ),
        professor_transcript=(
            "Objetivo simples: o que está no texto versus o que vocês concluem. "
            "No e-mail, o fato é a não aprovação agora. Tom de irritação já é leitura. "
            "Usem a pergunta-guia antes de opinar."
        ),
    ),
    LessonNoteSeed(
        lesson_key="estrutura_parecer",
        summary=(
            "Parecer em três blocos: Contexto, Análise e Recomendação. "
            "Caso: atraso do fornecedor crítico pedido por operações. "
            "Regra: não misturar ação na análise."
        ),
        unclear_points=(
            "Parte da turma ainda coloca a sugestão no meio da Análise. "
            "Pedi reescrever esse bloco só com fatos e interpretação."
        ),
        professor_transcript=(
            "Cada bloco responde a uma pergunta. Contexto: quem pediu o quê. "
            "Análise: o que aconteceu e o que significa, sem recomendar ainda. "
            "Recomendação: a ação. Se misturar, o leitor se perde."
        ),
    ),
    LessonNoteSeed(
        lesson_key="primeiro_rascunho",
        summary=(
            "Roteiro curto: Contexto, Análise, Recomendação sem polir estilo. "
            "Marcar [?] onde faltar dado. Critério: alguém de fora entende problema e proposta."
        ),
        unclear_points=(
            "Vários travaram tentando deixar o texto «bonito» cedo. "
            "Reforcei: frase curta primeiro, estilo depois."
        ),
        professor_transcript=(
            "Hoje é rascunho legível, não entrega final. Contexto em 3 ou 4 frases. "
            "Marquem [?] onde falta informação. Leiam um trecho em voz alta e digam "
            "onde o raciocínio ainda não fecha."
        ),
    ),
    LessonNoteSeed(
        lesson_key="revisao_pares",
        summary=(
            "Revisão em pares com foco em clareza. Trecho do projeto atrasado e a "
            "recomendação de trocar o fornecedor. Checklist: contexto, fato vs interpretação, "
            "recomendação alinhada ao pedido."
        ),
        unclear_points=(
            "Feedback ainda sai genérico («melhorar a clareza»). "
            "Pedi apontar o trecho e fazer uma pergunta ao autor."
        ),
        professor_transcript=(
            "Feedback útil aponta trecho e pergunta. Antes de sugerir trocar fornecedor, "
            "o que vocês perguntariam ao autor? O contexto deixa claro o pedido? "
            "A análise separa fato de interpretação?"
        ),
    ),
    LessonNoteSeed(
        lesson_key="argumentacao",
        summary=(
            "Argumentar com evidência. Analisamos o trecho com «acredito», «sempre» e «parece». "
            "Reformulamos mantendo só o que o caso sustenta."
        ),
        unclear_points=(
            "Alguns só trocaram a palavra e mantiveram a opinião sem dado. "
            "Próximo passo: sublinhar o conectivo e exigir fato antes."
        ),
        professor_transcript=(
            "Sublinhem «acredito», «parece», «sempre». Tem fato antes? Se não tiver, "
            "a frase não entra. Reformulem só com o que o texto ou o caso sustentam."
        ),
    ),
    LessonNoteSeed(
        lesson_key="entrega_final",
        summary=(
            "Checklist de entrega: leitura em voz alta, blocos fáceis de achar, "
            "assunto com posição, anexos citados de fato anexados. "
            "Simularam e-mail de entrega."
        ),
        unclear_points=(
            "Títulos ainda genéricos («Parecer fornecedor»). "
            "Alguns esqueceram de citar o anexo no corpo."
        ),
        professor_transcript=(
            "Antes de enviar: leiam em voz alta uma vez. Em dez segundos dá para achar "
            "contexto, análise e recomendação? O assunto deixa clara a posição? "
            "Se citou anexo, ele está anexado. Senão, não enviem."
        ),
    ),
]
