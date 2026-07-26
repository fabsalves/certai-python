"""Hand-written assessment / gap / micro-score pools for the demo seed (no AI)."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

# assessment, gaps
TextPair = tuple[str, str]


def _null_pool(*assessments: str) -> list[TextPair]:
    return [(a, "") for a in assessments]


# ---------------------------------------------------------------------------
# Lesson assessments: lesson_key -> level_key -> >=4 variations
# level_key: high|medium|low|very_low|null
# ---------------------------------------------------------------------------

LESSON_TEXTS: dict[str, dict[str, list[TextPair]]] = {
    "leitura_critica": {
        "high": [
            (
                "Frase «Não vou aprovar isso agora.» marcada como fato. Irritação e conflito "
                "entraram como leitura. Pergunta-guia saiu sem eu pedir.",
                "Manter o hábito de apontar a frase-base antes de opinar.",
            ),
            (
                "No e-mail interno, separou o literal do tom. Trouxe trecho do trabalho e fez "
                "a mesma divisão. Explicou a diferença com as próprias palavras.",
                "",
            ),
            (
                "Testou «Isso está escrito ou estou supondo?» em cada conclusão. Não aprovou "
                "interpretação sem apontar trecho.",
                "Praticar em mensagens mais longas do dia a dia.",
            ),
            (
                "Classificação limpa no exemplo. Fato numa coluna, suposição na outra. O trecho "
                "próprio veio com a mesma disciplina.",
                "",
            ),
        ],
        "medium": [
            (
                "Pegou o fato do e-mail («não vou aprovar isso agora»). Ainda fala de «clima» "
                "como se estivesse no texto.",
                "Apontar a frase literal antes de qualquer comentário sobre intenção.",
            ),
            (
                "Conceito ok quando guiado. Sozinho, mistura suposição sobre o remetente na "
                "mesma resposta do fato.",
                "Usar a pergunta-guia em voz alta em todo trecho novo.",
            ),
            (
                "Explicou fato versus interpretação de forma aceitável. Na aplicação ao e-mail "
                "ainda hesita.",
                "Refazer o exercício: lista «está escrito» e lista «estou supondo».",
            ),
            (
                "Separa bem com apoio. Sem apoio, rotula tom como conteúdo do e-mail.",
                "Mais um e-mail curto do próprio contexto antes da próxima aula.",
            ),
        ],
        "low": [
            (
                "Trata irritação e conflito como se estivessem escritos em «Não vou aprovar "
                "isso agora.». Pergunta-guia quase não aparece.",
                "Revisar: fato = frase apontável; interpretação = conclusão. Refazer a classificação.",
            ),
            (
                "Confunde literal com leitura emocional. Explicação da diferença fica vaga.",
                "Voltar aos três passos do material e aplicar no e-mail de exemplo.",
            ),
            (
                "Identifica a frase do e-mail e logo empilha intenções sem marcar interpretação.",
                "Duas listas explícitas: o que está escrito e o que está supondo.",
            ),
            (
                "Trecho do trabalho veio quase só com opinião. Pouca leitura crítica.",
                "Repetir a prática do material com tutoria.",
            ),
        ],
        "very_low": [
            (
                "Falou do e-mail como se o texto dissesse o que ele concluiu. Separação "
                "fato/interpretação não apareceu.",
                "Retomar o exemplo «Não vou aprovar isso agora.» do zero.",
            ),
            (
                "Não classificou o e-mail. Não usou a pergunta-guia. Critério do material "
                "não aparece nas respostas.",
                "Reler os três passos e refazer a classificação com apoio.",
            ),
            (
                "Em todas as respostas sobre o e-mail interno, fato e leitura ficaram misturados.",
                "Reforço só em apontar frases literais.",
            ),
            (
                "Diferença central da aula não ficou evidenciada.",
                "Recomeçar pelo texto de exemplo antes de casos do trabalho.",
            ),
        ],
        "null": _null_pool(
            "Evidência insuficiente para julgar se separa fato de interpretação no e-mail "
            "«Não vou aprovar isso agora.».",
            "Participação mínima. Sem base para avaliar pergunta-guia ou classificação "
            "fato versus interpretação.",
            "Sem demonstração aplicável ao material de leitura crítica. Nível não atribuído.",
            "Evidência insuficiente sobre a prática com o e-mail interno ou trechos do trabalho.",
        ),
    },
    "estrutura_parecer": {
        "high": [
            (
                "No caso do fornecedor crítico: Contexto, Análise e Recomendação sem misturar "
                "ação na análise. Cada bloco responde à pergunta certa.",
                "Manter a disciplina dos três blocos em pareceres reais.",
            ),
            (
                "Pegou rascunho que jogava recomendação na Análise e reescreveu. Bloco ficou "
                "só com fatos e interpretação fundamentada.",
                "",
            ),
            (
                "Contexto com pedido e prazo. Análise sem opinião solta. Recomendação objetiva "
                "ligada ao pedido de operações.",
                "Enxugar o Contexto para 2 ou 3 frases.",
            ),
            (
                "Regra «cada bloco uma pergunta» aplicada. Esqueleto utilizável por leitor "
                "de fora.",
                "",
            ),
        ],
        "medium": [
            (
                "Usa os três blocos. No caso do fornecedor, a Recomendação ainda vaza para "
                "dentro da Análise.",
                "Reescrever a Análise sem verbos de ação até o terceiro bloco.",
            ),
            (
                "Contexto e Recomendação ok. Análise mistura opinião sem amarrar fato.",
                "Na Análise: frases de fato do caso de um lado, interpretação do outro.",
            ),
            (
                "Estrutura entendida. Contexto longo demais; pedido de operações pouco claro.",
                "Limitar Contexto a 2 ou 3 frases: quem pediu o quê e prazo.",
            ),
            (
                "Blocos presentes. Fronteira Análise/Recomendação ainda oscila.",
                "Checklist: a Análise responde o que aconteceu e o que significa, sem o que fazer.",
            ),
        ],
        "low": [
            (
                "Parecer em fluxo único. Contexto, Análise e Recomendação não ficam "
                "identificáveis no caso do fornecedor.",
                "Usar o esqueleto do material e preencher um bloco por vez.",
            ),
            (
                "Ação sugerida aparece no meio da Análise com frequência.",
                "Regra: zero recomendação até o terceiro bloco.",
            ),
            (
                "Contexto incompleto (falta pedido ou prazo). Análise com opinião solta.",
                "Refazer o exercício da área de operações com o modelo do material.",
            ),
            (
                "Leitor não acha os três blocos em poucos segundos.",
                "Praticar com títulos explícitos nos três blocos.",
            ),
        ],
        "very_low": [
            (
                "Texto sobre o atraso do fornecedor mistura pedido, juízo e ação sem ordem. "
                "Três blocos não aparecem.",
                "Retomar o modelo Contexto / Análise / Recomendação do material.",
            ),
            (
                "Perguntas de cada bloco embaralhadas. Recomendação e fato no mesmo parágrafo.",
                "Reforço só com o esqueleto fixo.",
            ),
            (
                "Estrutura não aplicada ao caso de operações.",
                "Recomeçar pelo modelo antes de redigir.",
            ),
            (
                "Organização do parecer sem evidência de uso.",
                "Revisar o objetivo da aula e o exemplo do fornecedor crítico.",
            ),
        ],
        "null": _null_pool(
            "Evidência insuficiente de que organiza o parecer em Contexto, Análise e Recomendação.",
            "Conversa não mostrou aplicação ao caso do fornecedor crítico. Nível não atribuído.",
            "Sem base para avaliar se evita misturar recomendação na análise.",
            "Participação sem demonstração da estrutura de três blocos.",
        ),
    },
    "primeiro_rascunho": {
        "high": [
            (
                "Roteiro de 15 a 20 minutos cumprido. Contexto em 3 ou 4 frases. Análise com "
                "[?] onde faltava dado. Recomendação clara. Critério de pronto ok.",
                "",
            ),
            (
                "Não poliu estilo cedo. Leu trecho em voz alta e apontou onde o raciocínio "
                "não fechava. Bom uso de [?].",
                "Mesmo roteiro em pedidos reais com prazo curto.",
            ),
            (
                "Rascunho compreensível por alguém de fora. Frases curtas. Revisou só o "
                "fechamento lógico.",
                "",
            ),
            (
                "Ordem certa: escrever primeiro, polir depois. Três blocos na sequência.",
                "Cronometrar as três partes para ganhar ritmo.",
            ),
        ],
        "medium": [
            (
                "Rascunho utilizável. Ainda perde tempo polindo frase no meio do primeiro passe.",
                "Proibir revisão de estilo até marcar todos os [?].",
            ),
            (
                "Contexto e Recomendação ok. Análise curta demais ou sem [?] onde falta dado.",
                "Explicitar lacunas com [?] antes de seguir.",
            ),
            (
                "Critério de pronto entendido. Leitor ainda completa lacunas não marcadas.",
                "Ler em voz alta e só então listar o que falta.",
            ),
            (
                "Produz texto. Ordem Contexto → Análise → Recomendação às vezes inverte.",
                "Usar o roteiro do material como checklist de tempo.",
            ),
        ],
        "low": [
            (
                "Trava no início buscando texto «bonito». Rascunho não fica legível no tempo "
                "da aula.",
                "Forçar frases curtas e [?]. Estilo só depois do raciocínio fechar.",
            ),
            (
                "Polimento e invenção de dado no mesmo passe. Não marca [?].",
                "Não inventar. Marcar lacuna. Seguir o roteiro de 15 a 20 min.",
            ),
            (
                "Rascunho opaco. Leitor externo não entende problema nem proposta.",
                "Recomeçar pelo Contexto em 3 ou 4 frases sobre o caso.",
            ),
            (
                "Pouco avanço no rascunho rápido. Ainda revisa estilo cedo.",
                "Refazer o exercício com timer por bloco.",
            ),
        ],
        "very_low": [
            (
                "Sem rascunho utilizável. Sem [?]. Roteiro da aula não aparece.",
                "Retomar o objetivo: rascunho legível sem polir demais.",
            ),
            (
                "Sem evidência de passagem pelos três blocos no tempo proposto.",
                "Prática guiada só com o roteiro do material.",
            ),
            (
                "Critério de pronto não atendido. Alguém de fora não entende problema e proposta.",
                "Recomeçar pelo Contexto curto.",
            ),
            (
                "Primeiro rascunho sem demonstração suficiente.",
                "Reforço com leitura em voz alta de um parágrafo só.",
            ),
        ],
        "null": _null_pool(
            "Evidência insuficiente de rascunho (Contexto/Análise/Recomendação) e de uso de [?].",
            "Sem base para avaliar se segue o roteiro de 15 a 20 minutos.",
            "Participação sem demonstração do critério de pronto do rascunho.",
            "Sem trecho lido ou descrito que permita julgar o primeiro rascunho.",
        ),
    },
    "revisao_pares": {
        "high": [
            (
                "Checklist no trecho do projeto atrasado: questionou contexto, marcou "
                "«equipe não se empenhou» como interpretação, perguntou se trocar o "
                "fornecedor responde ao pedido. Feedback com trecho e pergunta ao autor.",
                "",
            ),
            (
                "Feedback específico, não genérico. Perguntaria de onde veio a conclusão "
                "sobre empenho antes de sugerir mudança de texto.",
                "Manter esse padrão em revisões reais.",
            ),
            (
                "Foco em clareza, não em estilo. Checklist completo. Pergunta-guia ao autor.",
                "",
            ),
            (
                "Viu que «trocar fornecedor» salta etapas. Pediu o pedido inicial antes de "
                "validar a ação.",
                "Modelar uma reformulação do trecho para o colega.",
            ),
        ],
        "medium": [
            (
                "Usa o checklist. Feedback ainda oscila entre genérico e específico.",
                "Citar trecho e fazer uma pergunta concreta ao autor.",
            ),
            (
                "Vê o problema de fato vs interpretação no trecho. Pergunta ao autor fica fraca.",
                "Praticar: «o leitor vai entender de onde veio X?»",
            ),
            (
                "Com orientação, revisa clareza. Sozinho, comenta estilo cedo demais.",
                "Checklist primeiro. Estilo só se a clareza já estiver ok.",
            ),
            (
                "Três itens do checklist ok. Às vezes deixa «trocar fornecedor» passar sem "
                "questionar o pedido.",
                "Sempre perguntar: a recomendação responde ao pedido inicial?",
            ),
        ],
        "low": [
            (
                "Feedback genérico («melhorar a clareza») sem apontar trecho do exemplo.",
                "Apontar a frase e sugerir uma pergunta ao autor.",
            ),
            (
                "Foca em estilo. Quase não usa o checklist (contexto / fato / recomendação).",
                "Revisar só com os três itens do material.",
            ),
            (
                "Aceita «a equipe não se empenhou» como fato sem questionar.",
                "Marcar interpretação e pedir evidência ao autor.",
            ),
            (
                "Revisão em pares com foco em clareza ainda frágil.",
                "Refazer o exercício do trecho com o checklist ao lado.",
            ),
        ],
        "very_low": [
            (
                "Checklist não aplicado. Feedback útil sobre o trecho dado não apareceu.",
                "Retomar objetivo: clareza, não estilo bonito.",
            ),
            (
                "Sem pergunta ao autor. Sem análise do trecho do projeto.",
                "Prática guiada com o exemplo do material.",
            ),
            (
                "Comentários não distinguem contexto, análise e recomendação no texto do colega.",
                "Reforço só com o checklist.",
            ),
            (
                "Revisão em pares sem demonstração suficiente.",
                "Recomeçar pelo trecho do projeto atrasado e «trocar fornecedor».",
            ),
        ],
        "null": _null_pool(
            "Evidência insuficiente de aplicação do checklist de revisão em pares.",
            "Sem base para avaliar feedback sobre o trecho do projeto atrasado.",
            "Participação sem demonstração de pergunta útil ao autor.",
            "Não é possível julgar o foco em clareza versus estilo.",
        ),
    },
    "argumentacao": {
        "high": [
            (
                "No trecho, separou o que tem evidência do que é opinião («acredito», "
                "«sempre», «parece»). Reformulou só com o que o caso sustenta. Sem "
                "absolutismos vazios.",
                "",
            ),
            (
                "Uma ideia por parágrafo. Afirmações amarradas a fato. Tirou «desinteresse» "
                "sem prova. Identificou retórica vazia.",
                "Seguir o teste dos conectivos de opinião em pareceres reais.",
            ),
            (
                "Reformulação limpa. Juízos sem amparo saíram. Ficou o que o contrato e o "
                "caso permitem afirmar.",
                "",
            ),
            (
                "Sublinhou conectivos e exigiu fato antes deles. Argumentação objetiva.",
                "Praticar com um parágrafo adicional do próprio trabalho.",
            ),
        ],
        "medium": [
            (
                "Identifica «acredito/parece/sempre». Reformulação ainda deixa opinião "
                "disfarçada.",
                "Depois de sublinhar, riscar tudo que não tiver fato imediatamente antes.",
            ),
            (
                "Teste rápido entendido. Às vezes mantém «sempre atrasa» sem dado.",
                "Trocar absolutismos por ocorrência observada e datada.",
            ),
            (
                "Em exercício guiado, separa bem. Sozinho, mistura retórica na mesma frase "
                "do fato.",
                "Uma ideia por parágrafo. Fato e juízo em frases separadas.",
            ),
            (
                "Intenção de amarrar evidência ok. Reformulação do trecho ainda irregular.",
                "Reescrever o parágrafo inteiro só com o que o caso sustenta.",
            ),
        ],
        "low": [
            (
                "Ainda argumenta com «parece» e «acredito» como se bastassem. Pouca amarração "
                "a fato.",
                "Sublinhar conectivos de opinião e só então reescrever.",
            ),
            (
                "Aceita «sempre atrasa» e «desinteresse» sem pedir prova.",
                "Sem fato do caso, a afirmação não entra.",
            ),
            (
                "Reformulação troca palavras e mantém juízo sem evidência.",
                "Listar o que o trecho e o caso realmente autorizam antes de redigir.",
            ),
            (
                "Argumentação com evidência ainda frágil.",
                "Refazer a análise do trecho do material com o teste rápido.",
            ),
        ],
        "very_low": [
            (
                "Não separou evidência de opinião no trecho. Retórica vazia intacta.",
                "Retomar: ideia por parágrafo e fato antes da afirmação.",
            ),
            (
                "Teste dos conectivos («acredito», «parece», «sempre») não aplicado.",
                "Prática guiada só com o trecho do material.",
            ),
            (
                "Reformulação não sustentada pelo caso.",
                "Reforço em argumentação objetiva.",
            ),
            (
                "Competência desta aula sem demonstração suficiente.",
                "Recomeçar pelo trecho de rescisão/fornecedor do material.",
            ),
        ],
        "null": _null_pool(
            "Evidência insuficiente sobre argumentação com evidência no trecho da aula.",
            "Sem base para avaliar se identifica conectivos de opinião ou reformula com fato.",
            "Participação sem demonstração do teste rápido do material.",
            "Não é possível atribuir nível de compreensão nesta aula.",
        ),
    },
    "entrega_final": {
        "high": [
            (
                "Checklist completo: leitura em voz alta, blocos visíveis em poucos segundos, "
                "assunto com posição, anexos citados e presentes. E-mail de entrega claro.",
                "",
            ),
            (
                "Título objetivo (assunto + resposta). Corpo alinhado aos três blocos. Indicou "
                "o último ponto que ainda revisaria.",
                "Manter o checklist antes de todo envio real.",
            ),
            (
                "Entrega coerente com o parecer da trilha. Anexos ok. Posição em uma frase.",
                "",
            ),
            (
                "Passou pelos quatro itens sem atalho. Assunto deixava clara a posição do parecer.",
                "Lembrete pessoal com os quatro itens do material.",
            ),
        ],
        "medium": [
            (
                "Quase pronto. Blocos ok. Título ainda genérico («Parecer fornecedor»).",
                "Assunto = tema + posição/resposta na mesma linha.",
            ),
            (
                "Leu em voz alta. Esqueceu de citar o anexo no corpo ou de confirmar o arquivo.",
                "Item 4 do checklist: anexo citado = anexo anexado.",
            ),
            (
                "Posição do parecer existe. Demora mais de 10 segundos para achar a Recomendação.",
                "Deixar os três blocos visualmente óbvios.",
            ),
            (
                "Entrega utilizável com furos pequenos no checklist.",
                "Rodar os quatro itens em voz alta antes de enviar.",
            ),
        ],
        "low": [
            (
                "Checklist incompleto. Título vago. Anexos não conferidos.",
                "Aplicar os quatro itens do material um a um na próxima entrega.",
            ),
            (
                "Assunto do e-mail e frase de posição mal simulados.",
                "Praticar: uma linha de assunto + uma frase de posição.",
            ),
            (
                "Blocos não identificáveis rápido. Leitura em voz alta não usada.",
                "Ler uma vez em voz alta e marcar onde tropeçar.",
            ),
            (
                "Padrão de entrega final ainda frágil.",
                "Refazer a simulação de envio com o checklist ao lado.",
            ),
        ],
        "very_low": [
            (
                "Checklist de entrega não apareceu. Assunto e anexos indefinidos.",
                "Retomar os quatro itens do material antes de qualquer envio.",
            ),
            (
                "Sem simulação de e-mail/PDF alinhada ao parecer.",
                "Prática guiada de assunto + posição + anexos.",
            ),
            (
                "Blocos e posição do parecer não aparecem na entrega.",
                "Reforço só com o checklist final.",
            ),
            (
                "Entrega final sem demonstração suficiente.",
                "Recomeçar pelo objetivo da aula e pelo checklist.",
            ),
        ],
        "null": _null_pool(
            "Evidência insuficiente de checklist de entrega (leitura, blocos, título, anexos).",
            "Sem base para avaliar assunto de e-mail ou frase de posição do parecer.",
            "Participação sem demonstração da entrega final.",
            "Não é possível atribuir nível nesta aula.",
        ),
    },
}


MODULE_TEXTS: dict[str, dict[str, list[TextPair]]] = {
    "fundamentos": {
        "high": [
            (
                "No módulo Fundamentos: fato vs interpretação no e-mail de exemplo, três blocos "
                "do parecer e rascunho sem polir cedo. Base para o parecer ok.",
                "Seguir aplicando a pergunta-guia e o esqueleto em pedidos reais.",
            ),
            (
                "Separa fato/interpretação. Organiza Contexto/Análise/Recomendação. Produz "
                "rascunho legível com [?].",
                "",
            ),
            (
                "As três aulas se reforçam. Leitura crítica alimenta a Análise. Estrutura e "
                "rascunho já saem utilizáveis.",
                "Manter o ritmo sem abandonar os [?].",
            ),
            (
                "Do e-mail «Não vou aprovar isso agora.» até o primeiro rascunho, o módulo "
                "ficou assimilado.",
                "",
            ),
        ],
        "medium": [
            (
                "Fundamentos presentes. Às vezes mistura recomendação na Análise ou polimento "
                "cedo no rascunho.",
                "Reforçar fronteira dos blocos e o roteiro de 15 a 20 minutos.",
            ),
            (
                "Leitura crítica ok na maior parte. Estrutura e rascunho ainda pedem disciplina.",
                "Revisar o esqueleto do parecer antes de cada novo texto.",
            ),
            (
                "Conceitos claros. Aplicação irregular nas três aulas.",
                "Escolher um ponto fraco (fato/interpretação ou blocos) e treinar de propósito.",
            ),
            (
                "Base suficiente para seguir. Lacunas pontuais nas aulas de Fundamentos.",
                "Revisitar a aula mais fraca do módulo com o material ao lado.",
            ),
        ],
        "low": [
            (
                "Fato/interpretação e blocos do parecer ainda instáveis.",
                "Priorizar reforço em leitura crítica e estrutura antes de acelerar a Prática.",
            ),
            (
                "Rascunho e organização do parecer abaixo do esperado para o módulo.",
                "Refazer os exercícios do e-mail e do fornecedor crítico.",
            ),
            (
                "As três aulas de Fundamentos não se conectam no uso.",
                "Plano curto de revisão das aulas 1 a 3.",
            ),
            (
                "Sinais fracos nas competências centrais do módulo.",
                "Apoio tutorial em estrutura de parecer e pergunta-guia.",
            ),
        ],
        "very_low": [
            (
                "Nas três aulas de Fundamentos, demonstração útil quase não aparece.",
                "Retomar do início: fato vs interpretação e esqueleto do parecer.",
            ),
            (
                "Sem base consolidada de leitura crítica, estrutura ou rascunho.",
                "Trilha de reforço em Fundamentos antes da Prática.",
            ),
            (
                "Compreensão do módulo muito baixa.",
                "Recomeçar pelos materiais das aulas 1 a 3 com acompanhamento.",
            ),
            (
                "Fundamentos não consolidados.",
                "Avaliar necessidade de aula extra de estrutura de parecer.",
            ),
        ],
        "null": _null_pool(
            "Nas aulas de Fundamentos, evidência de compreensão insuficiente. Nível do "
            "módulo não atribuído.",
            "Sem demonstração suficiente em leitura crítica, estrutura ou rascunho para "
            "avaliar o módulo.",
            "Participação no módulo sem base avaliável. Nível de Fundamentos não atribuído.",
            "Evidência insuficiente no conjunto das três primeiras aulas.",
        ),
    },
    "pratica": {
        "high": [
            (
                "Na Prática: revisa com checklist e pergunta ao autor, argumenta sem "
                "«acredito/sempre» vazios, fecha entrega com checklist completo.",
                "",
            ),
            (
                "Clareza na revisão. Reformulação sustentada. E-mail de entrega com posição clara.",
                "Manter o checklist de envio como hábito.",
            ),
            (
                "Transforma o parecer da trilha em texto revisado, argumentado e entregável.",
                "",
            ),
            (
                "As três aulas de Prática aparecem no resultado final.",
                "Seguir evitando absolutismos sem prova.",
            ),
        ],
        "medium": [
            (
                "Revisão e argumentação ok com falhas pontuais. Entrega às vezes com título "
                "genérico ou anexo esquecido.",
                "Fechar o checklist de entrega com rigor.",
            ),
            (
                "Avanço em pares e evidência. Ainda oscila na reformulação sem opinião.",
                "Sublinhar conectivos de opinião em todo parágrafo decisivo.",
            ),
            (
                "Módulo utilizável, ainda não estável.",
                "Reforçar a aula mais fraca entre revisão, argumentação e entrega.",
            ),
            (
                "Consegue entregar. Lacunas de clareza ou de evidência em pontos isolados.",
                "Revisar o trecho-exemplo de argumentação e o checklist final.",
            ),
        ],
        "low": [
            (
                "Feedback genérico. Argumentação com retórica. Entrega incompleta.",
                "Priorizar checklist de pares e teste de conectivos de opinião.",
            ),
            (
                "Revisão, argumentação e entrega final irregulares.",
                "Plano de reforço nas três aulas do módulo.",
            ),
            (
                "Clareza e evidência na etapa prática não se sustentam bem.",
                "Refazer os exercícios do trecho do projeto e do trecho com «acredito/sempre».",
            ),
            (
                "Módulo Prática abaixo do esperado.",
                "Apoio próximo na próxima entrega real.",
            ),
        ],
        "very_low": [
            (
                "Revisão, argumentação e entrega sem demonstração útil.",
                "Retomar os materiais das aulas 4 a 6 com acompanhamento.",
            ),
            (
                "Módulo Prática muito frágil.",
                "Aula extra de argumentação com evidência recomendada.",
            ),
            (
                "Competências práticas da trilha não consolidadas.",
                "Recomeçar pelo checklist de pares e pelo checklist de entrega.",
            ),
            (
                "Compreensão do módulo Prática muito baixa.",
                "Revisão integral do módulo antes de nova tentativa de entrega.",
            ),
        ],
        "null": _null_pool(
            "Nas aulas de Prática, evidência insuficiente. Nível do módulo não atribuído.",
            "Sem base para avaliar revisão em pares, argumentação ou entrega final em conjunto.",
            "Participação insuficiente no módulo Prática para julgar compreensão.",
            "Evidência insuficiente no segundo módulo.",
        ),
    },
}


TRACK_TEXTS: dict[str, list[TextPair]] = {
    "high": [
        (
            "Na trilha Comunicação escrita no trabalho: fato vs interpretação, parecer em "
            "três blocos, rascunho disciplinado, revisão em pares, argumentação com "
            "evidência e entrega com checklist. Pronto para pareceres reais com supervisão leve.",
            "",
        ),
        (
            "Fundamentos e Prática alinhados. Escreve com clareza, amarra fato e entrega "
            "com posição explícita.",
            "Manter os checklists como hábito operacional.",
        ),
        (
            "Do e-mail «Não vou aprovar isso agora.» à entrega final, o fio da competência "
            "aparece. Pareceres claros e objetivos.",
            "",
        ),
        (
            "Trilha assimilada. Poucas lacunas. Autonomia alta na escrita profissional curta.",
            "Continuar evitando absolutismos sem prova em contextos novos.",
        ),
    ],
    "medium": [
        (
            "Base de Fundamentos e Prática presente. Lacunas recorrentes: mistura "
            "fato/interpretação, recomendação na análise, ou argumentação com opinião. "
            "Entrega com revisão.",
            "Priorizar o ponto mais frágil das aulas irregulares e reforçá-lo.",
        ),
        (
            "Parecer melhora quando usa os esqueletos. Sozinho ainda oscila.",
            "Checklist único: pergunta-guia + três blocos + conectivos de opinião + entrega.",
        ),
        (
            "Trechos fortes em algumas aulas. Buracos em outras. Nível médio global.",
            "Plano curto nas lacunas mais ricas das avaliações de aula.",
        ),
        (
            "Redige parecer utilizável. Qualidade depende do tema da aula. Ainda não está "
            "estável em toda a jornada.",
            "Revisar as aulas com nível baixo ou sem evidência antes de pedidos complexos.",
        ),
    ],
    "low": [
        (
            "Fundamentos e prática ainda não sustentam um parecer claro e objetivo de ponta "
            "a ponta.",
            "Reforço em leitura crítica, estrutura e argumentação com evidência antes de autonomia.",
        ),
        (
            "Dificuldade persistente: do fato/interpretação à entrega.",
            "Apoio nas aulas com very_low/low e checagem próxima do professor.",
        ),
        (
            "Ainda não redige pareceres confiáveis sem apoio intenso.",
            "Retomar Fundamentos com exercícios guiados. Só então acelerar a Prática.",
        ),
        (
            "Nível baixo na competência da trilha.",
            "Considerar aulas extras nos bloqueios mais frequentes (blocos do parecer e evidência).",
        ),
    ],
    "very_low": [
        (
            "Camadas de aula e módulo sem domínio mínimo para pareceres claros.",
            "Replanejar acompanhamento intensivo desde leitura crítica.",
        ),
        (
            "Jornada não consolidada. Risco alto de entrega opaca ou opinativa sem fato.",
            "Intervenção pedagógica antes de novos módulos avançados.",
        ),
        (
            "Evidência agregada aponta very_low na competência da trilha.",
            "Recomeçar pelos materiais essenciais com tutoria.",
        ),
        (
            "No conjunto, a competência «redigir pareceres claros e objetivos» não aparece.",
            "Plano de recuperação completo da trilha.",
        ),
    ],
    "null": _null_pool(
        "Na trilha como um todo, evidência de compreensão nas aulas insuficiente. "
        "Nível da jornada não atribuído.",
        "Participação sem demonstração suficiente nas camadas de aula e módulo. "
        "Trilha sem nível.",
        "Evidência insuficiente para julgar a competência da trilha Comunicação escrita "
        "no trabalho.",
        "Sem base agregada avaliável. Nível da trilha não atribuído.",
    ),
}


@dataclass(frozen=True)
class MicroSeed:
    competency: str
    level: str  # Level value
    evidence: str


MICRO_POOLS: dict[str, dict[str, list[MicroSeed]]] = {
    "leitura_critica": {
        "high": [
            MicroSeed(
                "Separar fato de interpretação",
                "high",
                "Apontou «Não vou aprovar isso agora.» como fato e classificou tom "
                "como interpretação antes de opinar.",
            ),
            MicroSeed(
                "Pergunta-guia na leitura",
                "high",
                "Usou «Isso está escrito ou estou supondo?» no e-mail de exemplo sem "
                "ser lembrado.",
            ),
        ],
        "medium": [
            MicroSeed(
                "Separar fato de interpretação",
                "medium",
                "Identificou o fato do e-mail, mas comentou «clima» sem marcar como "
                "interpretação.",
            ),
            MicroSeed(
                "Pergunta-guia na leitura",
                "medium",
                "Aplicou a pergunta-guia quando lembrado. Ainda não é hábito.",
            ),
        ],
        "low": [
            MicroSeed(
                "Separar fato de interpretação",
                "low",
                "Tratou irritação como se estivesse escrita no e-mail interno.",
            ),
            MicroSeed(
                "Pergunta-guia na leitura",
                "low",
                "Não usou a pergunta-guia ao classificar o trecho.",
            ),
        ],
        "very_low": [
            MicroSeed(
                "Separar fato de interpretação",
                "very_low",
                "Não distinguiu o literal do e-mail da conclusão própria.",
            ),
        ],
    },
    "estrutura_parecer": {
        "high": [
            MicroSeed(
                "Blocos do parecer",
                "high",
                "Escreveu Contexto, Análise e Recomendação sem colocar ação na Análise "
                "(caso do fornecedor).",
            ),
            MicroSeed(
                "Análise sem recomendação",
                "high",
                "Reescreveu a Análise só com fatos e interpretação fundamentada.",
            ),
        ],
        "medium": [
            MicroSeed(
                "Blocos do parecer",
                "medium",
                "Usou os três blocos, com vazamento pontual de recomendação na Análise.",
            ),
        ],
        "low": [
            MicroSeed(
                "Blocos do parecer",
                "low",
                "Texto em fluxo único. Blocos pouco identificáveis no caso de operações.",
            ),
        ],
        "very_low": [
            MicroSeed(
                "Blocos do parecer",
                "very_low",
                "Não aplicou o esqueleto Contexto / Análise / Recomendação.",
            ),
        ],
    },
    "primeiro_rascunho": {
        "high": [
            MicroSeed(
                "Rascunho sem polir cedo",
                "high",
                "Seguiu o roteiro de 15 a 20 min e marcou [?] onde faltava dado.",
            ),
            MicroSeed(
                "Critério de pronto do rascunho",
                "high",
                "Leitor externo entenderia problema e proposta apesar de imperfeições.",
            ),
        ],
        "medium": [
            MicroSeed(
                "Rascunho sem polir cedo",
                "medium",
                "Rascunho ok. Ainda perdeu tempo com estilo no primeiro passe.",
            ),
        ],
        "low": [
            MicroSeed(
                "Rascunho sem polir cedo",
                "low",
                "Travou buscando texto bonito. Pouco avanço no roteiro.",
            ),
        ],
        "very_low": [
            MicroSeed(
                "Rascunho sem polir cedo",
                "very_low",
                "Não produziu rascunho utilizável nem usou [?].",
            ),
        ],
    },
    "revisao_pares": {
        "high": [
            MicroSeed(
                "Checklist de revisão em pares",
                "high",
                "Questionou contexto, fato vs interpretação e se trocar fornecedor "
                "responde ao pedido.",
            ),
            MicroSeed(
                "Feedback com trecho e pergunta",
                "high",
                "Apontou trecho confuso e perguntou ao autor a origem da conclusão "
                "sobre empenho.",
            ),
        ],
        "medium": [
            MicroSeed(
                "Checklist de revisão em pares",
                "medium",
                "Passou pelo checklist. Feedback ainda meio genérico.",
            ),
        ],
        "low": [
            MicroSeed(
                "Feedback com trecho e pergunta",
                "low",
                "Disse só «melhorar a clareza» sem apontar trecho.",
            ),
        ],
        "very_low": [
            MicroSeed(
                "Checklist de revisão em pares",
                "very_low",
                "Não aplicou o checklist ao trecho do material.",
            ),
        ],
    },
    "argumentacao": {
        "high": [
            MicroSeed(
                "Argumentação com evidência",
                "high",
                "Removeu «acredito/sempre/parece» sem fato e reformulou só com o caso.",
            ),
            MicroSeed(
                "Evitar absolutismos sem prova",
                "high",
                "Trocou «sempre atrasa» por ocorrência observada sustentada.",
            ),
        ],
        "medium": [
            MicroSeed(
                "Argumentação com evidência",
                "medium",
                "Identificou conectivos de opinião. Reformulação ainda deixou juízo residual.",
            ),
        ],
        "low": [
            MicroSeed(
                "Argumentação com evidência",
                "low",
                "Manteve retórica («parece», «desinteresse») sem amarração a fato.",
            ),
        ],
        "very_low": [
            MicroSeed(
                "Argumentação com evidência",
                "very_low",
                "Não separou evidência de opinião no trecho da aula.",
            ),
        ],
    },
    "entrega_final": {
        "high": [
            MicroSeed(
                "Checklist de entrega",
                "high",
                "Leu em voz alta, blocos visíveis, assunto com posição, anexos conferidos.",
            ),
            MicroSeed(
                "Assunto e posição do parecer",
                "high",
                "Simulou e-mail com assunto objetivo e frase de posição clara.",
            ),
        ],
        "medium": [
            MicroSeed(
                "Checklist de entrega",
                "medium",
                "Quase completo. Título ainda genérico ou anexo não citado.",
            ),
        ],
        "low": [
            MicroSeed(
                "Checklist de entrega",
                "low",
                "Entrega sem passagem clara pelos quatro itens do checklist.",
            ),
        ],
        "very_low": [
            MicroSeed(
                "Checklist de entrega",
                "very_low",
                "Não evidenciou checklist nem simulação de envio.",
            ),
        ],
    },
}


def level_key(level: str | None) -> str:
    return "null" if level is None else level


def pick_text(
    pool: list[TextPair],
    rng: Random,
    *,
    salt: int,
) -> TextPair:
    return pool[(salt + rng.randint(0, 10_000)) % len(pool)]


def lesson_text(lesson_key: str, level: str | None, rng: Random, salt: int) -> TextPair:
    key = level_key(level)
    return pick_text(LESSON_TEXTS[lesson_key][key], rng, salt=salt)


def module_text(module_key: str, level: str | None, rng: Random, salt: int) -> TextPair:
    key = level_key(level)
    return pick_text(MODULE_TEXTS[module_key][key], rng, salt=salt)


def track_text(level: str | None, rng: Random, salt: int) -> TextPair:
    key = level_key(level)
    return pick_text(TRACK_TEXTS[key], rng, salt=salt)


def pick_micros(
    lesson_key: str,
    level: str | None,
    rng: Random,
    *,
    mode: str,
    salt: int,
) -> list[MicroSeed]:
    if mode == "none" or level is None:
        return []
    bucket = MICRO_POOLS[lesson_key].get(level) or MICRO_POOLS[lesson_key].get("low") or []
    if not bucket:
        return []
    if mode == "sparse":
        if salt % 3 != 0:
            return []
        return [bucket[salt % len(bucket)]]
    # full: 1 or 2
    n = 1 if len(bucket) == 1 else 1 + (salt % 2)
    start = salt % len(bucket)
    out = []
    for j in range(n):
        out.append(bucket[(start + j) % len(bucket)])
    return out
