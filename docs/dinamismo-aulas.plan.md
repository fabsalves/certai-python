---
name: Dinamismo de Aulas
overview: Separa conteúdo planejado de conteúdo ministrado. Uma sessão de aula passa a declarar sua cobertura real — segmentos por aula, com pendência e excedente explícitos — proposta pela IA a partir do próprio relato e confirmada pelo professor. O escopo ministrado passa a ser a autoridade na conversa da Lira e na avaliação, sem alterar sequência de aulas, dispatch, roteamento inbound nem o invariante de uma aula ATIVA por aluno.
todos:
  - id: fase-1-modelo
    content: "Fase 1: LessonCoverage (append-only) + migration 019 + schemas"
    status: completed
  - id: fase-2-proposta
    content: "Fase 2: coverage_service — proposta pela IA (janela de aulas candidatas + pendências) e leitura de cobertura/pendência vigente"
    status: completed
  - id: fase-3-persistencia
    content: "Fase 3: complete_lesson persiste a cobertura confirmada; consolidação recebe a cobertura como entrada"
    status: completed
  - id: fase-4-contexto
    content: "Fase 4: ContextBundle.taught_scope — escopo ministrado vira a âncora da Lira; excedente entra descrito, nunca como catálogo futuro"
    status: completed
  - id: fase-5-avaliacao
    content: "Fase 5: avaliador passa a ter o ministrado como autoridade; pendência declarada como não ministrada; carryover sinalizado"
    status: completed
  - id: fase-6-frontend
    content: "Fase 6: confirmação da proposta em LessonReportCapture + pendência visível no CohortProgressPanel"
    status: completed
  - id: fase-7-verificacao
    content: "Fase 7: bin/verify-dinamismo — os três cenários da seção 2 do doc ponta a ponta + regressão do caminho feliz"
    status: completed
isProject: false
---

# Plano: Dinamismo de Aulas no CertAI

**Projeto:** `certai-python` · branch `main`
**Origem:** `docs/certai-python/CERTAI_2.DOC` (CertAI - Produto · Dinamismo de Aulas)
**Referências:** [`student_lesson_progression.plan.md`](student_lesson_progression.plan.md), [`avaliacao-camadas.plan.md`](avaliacao-camadas.plan.md), [`../README.md`](../README.md)

**Premissa:** o produto atual não está errado. O MVP modelou o caminho feliz com coerência
— inclusive a restrição estrutural "não ensine o futuro". Este pacote é a evolução natural:
acomodar aula incompleta, adiantada e composta **dentro** dessa arquitetura, sem reescrevê-la.

**Princípios mantidos:** a IA decide, o código persiste · restrição vira estrutura · motor
único, o que diverge é o contexto · projeto enxuto · sem migração de dados (assumir `bin/db-reset`).

---

## Fase 0 — Achados (validação contra o código)

### F0.1 — Os três cenários hoje

| Cenário | Estado atual | Onde |
|---|---|---|
| Incompleta | Aula fecha inteira. O que faltou vira `level: null` + texto livre em `gaps` — prosa, não estado acionável | `services/student_progress_service.py` (`close_by_advance`) |
| Adiantada | Impossível registrar. O excedente é dobrado na nota da aula corrente pela consolidação | `api/v1/cohorts.py:1276` |
| Composta | Impossível registrar. Uma nota tem `lesson_id` singular e obrigatório | `models/assessment.py:90` |

`partial_lesson_ids` (`api/v1/cohorts.py:833`) **não** é conteúdo parcial: significa "algumas
turmas do módulo fecharam, outras não". Nome colide com o conceito novo — não reaproveitar.

### F0.2 — Planejado é premissa estrutural, não regra de prompt

`CONSOLIDATION_SYSTEM_PROMPT` (`services/lesson_completion_service.py:35`) **nunca recebe
`lesson.content`**. A IA que consolida não tem o planejado no contexto: não compara, e não
teria como discordar. O código arquiva o resultado sob o `lesson_id` que o endpoint já fixou.

Depois o `ContextBuilder` entrega `lesson.content` (planejado) sob `## Current lesson content`,
e o `SYSTEM_BASE` manda ancorar as perguntas nele (`ai/engine.py:30`).

### F0.3 — Excedente não é descartado; é arquivado no lugar errado

`professor_transcript` guarda o relato íntegro, e a consolidação dobra o material adiantado no
`summary`/`knowledge_base` **da aula corrente**. Como `_notes()` entrega o `knowledge_base` da
aula corrente (`ai/context_builder.py:246`), conteúdo da aula seguinte fica disponível à Lira
enquanto o aluno está na aula atual — a garantia estrutural do README é contornada exatamente
no cenário adiantado. Corrigir isso é efeito colateral desejado deste pacote: o excedente passa
a entrar **descrito e escopado**, em vez de vazar como base de conhecimento.

### F0.4 — Avaliação mistura planejado e ministrado sem hierarquia

`services/assessment/lesson_assessment_service.py:86-87` monta `## Material da aula`
(`lesson.content`, planejado) e `## Escopo da turma (relato do professor)` (nota, ministrado),
sem dizer qual define o escopo. Agravante: `EVALUATOR_SYSTEM_PROMPT` manda pesar "a cobertura
do escopo" (`services/assessment/evaluator.py:35`) — numa aula incompleta isso funciona como
projetado e **rebaixa o aluno por conteúdo que ele nunca recebeu**.

### F0.5 — Consumidores do contexto (raio de alcance da Fase 4)

Ambos passam por `build_lesson()` + `to_system_blocks()`, então um campo novo no bundle
propaga sem alteração local:

- `services/realtime/instructions_builder.py:177` — voz Realtime
- `services/playground_context_service.py:28` — playground admin (lista campos explicitamente
  na linha 120; incluir o novo)

---

## Desenho

### A sessão declara sua cobertura; a sequência não muda

Uma chamada de `complete_lesson` é **uma sessão**. Ela mantém sua **aula âncora**
(`CohortLessonNote.lesson_id` = a próxima aula aberta da turma) e ganha uma **cobertura real**:
segmentos que podem apontar para aulas anteriores (composta) ou posteriores (adiantada).

```
Sessão (CohortLessonNote, âncora = aula 2)
├── LessonCoverage · aula 1 · carryover · full     "fechou tom formal, que faltou"
├── LessonCoverage · aula 2 · planned   · partial  "cobriu coesão; falta coerência"
└── LessonCoverage · aula 3 · advance   · partial  "adiantou o conceito de registro"
```

**O que isso preserva intacto:** a âncora continua sendo a próxima aula aberta da turma, então
o guard `"Só é possível encerrar a aula atual da sua turma"` **não precisa afrouxar**. Dispatch,
`Conversation` (única por aula), `StudentLessonProgress` e o invariante de uma ATIVA por aluno
continuam key-ando pela âncora — zero alteração nesses fluxos. Composta e adiantada deixam de
exigir "fechar duas aulas": viram segmentos de cobertura de uma sessão só.

**Onde o aluno conversa:** uma conversa por sessão, na âncora. O escopo real da sessão — cauda
da anterior + o que foi dado hoje + o que foi adiantado — é o que a Lira explora e o que a
avaliação cobra. É o "cobrar exatamente o que ele recebeu" da seção 4 do doc.

**Pendência é derivada, não é estado paralelo.** A pendência vigente de uma aula para uma turma
é o campo `pending` da linha de cobertura mais recente daquela aula naquela turma. Append-only,
leitor pega a última — mesma convenção já usada por `StudentAssessment`
(`models/assessment.py:52`). Uma sessão futura que cobre a cauda escreve uma linha nova com
`pending` vazio, e a pendência se resolve sem UPDATE nem máquina de estados.

### Como o professor informa

O professor grava/escreve o relato como hoje. Antes de submeter, o front chama uma proposta
síncrona: a IA recebe o relato + o conteúdo planejado de uma **janela de aulas candidatas**
(anterior, âncora, duas seguintes) + as pendências vigentes, e devolve a segmentação. O
professor confirma ou ajusta num toque, e a cobertura confirmada vai no mesmo submit.

`complete-lesson` **continua sem LLM na request** (fast path preservado, README). A chamada de
IA fica num endpoint próprio, ao lado de `/transcribe-report`, que já faz trabalho de IA síncrono.

> **Nota sobre "não ensine o futuro":** esta é a única chamada de LLM que recebe conteúdo de
> aulas futuras. É contexto **do professor**, não do aluno — não passa pelo motor da Lira nem
> pelo bundle do aluno. O excedente só chega ao aluno como texto descritivo do que foi
> efetivamente dito em sala, nunca como catálogo da aula futura.

---

## Fase 1 — Modelo de cobertura

**`models/assessment.py`** — junto de `CohortLessonNote`, que é o registro da sessão.

```python
class CoverageKind(str, enum.Enum):
    PLANNED = "planned"      # segmento da própria aula âncora
    CARRYOVER = "carryover"  # cauda de uma aula anterior, fechada nesta sessão
    ADVANCE = "advance"      # conteúdo de uma aula posterior, dado adiantado

class CoverageExtent(str, enum.Enum):
    FULL = "full"
    PARTIAL = "partial"

class LessonCoverage(Base):
    """O que uma sessão de aula efetivamente cobriu, por aula. Append-only:
    a cobertura vigente de uma aula é a linha mais recente daquela turma."""
    __tablename__ = "lesson_coverage"

    note_id      -> cohort_lesson_notes.id (CASCADE, index)
    cohort_id    -> cohorts.id (CASCADE, index)         # denormalizado p/ leitura
    lesson_id    -> lessons.id (CASCADE, index)
    module_professor_id -> cohort_module_professors.id (RESTRICT, index)
    kind:   CoverageKind
    extent: CoverageExtent
    covered: Text = ""   # o que foi ministrado, em pt-BR
    pending: Text = ""   # o que esta aula ainda deve; "" quando nada
    source:  String(20)  # "ai" | "professor" — proposta aceita ou ajustada
```

`cohort_id` e `module_professor_id` são denormalizados de propósito: a leitura de pendência é
por turma-de-professor e roda no caminho quente do contexto e da avaliação.

**`alembic/versions/019_lesson_coverage.py`** — aditiva, sem backfill. Enums `native_enum=False`
(padrão do repo). Índice composto `(cohort_id, module_professor_id, lesson_id, created_at desc)`
para a query de pendência vigente.

**`schemas/__init__.py`** — `CoverageSegmentIn/Out`, `CoverageProposalIn/Out`.

**Não muda:** `CohortLessonNote.lesson_id` continua singular e obrigatório. É a âncora.

---

## Fase 2 — `services/coverage_service.py`

Arquivo plano na raiz de `services/`, como `lesson_completion_service.py` e
`student_progress_service.py`. Duas responsabilidades, ~150 linhas.

**Leitura (sem IA):**

- `current_pendings(db, cohort_id, module_professor_id, lesson_ids)` → `dict[lesson_id, str]`
  com a pendência vigente de cada aula (última linha, `pending` não vazio).
- `taught_scope_for(db, cohort_id, module_professor_id, lesson_id)` → o que foi ministrado
  naquela aula, agregando as linhas de cobertura que a tocaram (própria + carryover + advance).
- `candidate_window(db, cohort_id, anchor_lesson_id)` → aula anterior, âncora e as duas
  seguintes, via `ordered_active_lessons` (`services/track_structure.py`).

**Proposta (uma chamada de IA):**

- `propose_coverage(db, cohort_id, module_professor_id, anchor_lesson_id, transcript)`
  → `list[CoverageSegmentOut]`.

Prompt em pt-BR, no padrão de `CONSOLIDATION_SYSTEM_PROMPT`: recebe o relato, a janela de aulas
candidatas com título + conteúdo planejado, e as pendências vigentes. Devolve JSON com um array
de segmentos (`lesson_id`, `kind`, `extent`, `covered`, `pending`). Instrução central: **derivar
do relato o que foi efetivamente ministrado**, sem assumir que a aula seguiu o plano; não inventar
cobertura que o relato não sustenta; a âncora sempre presente, ainda que parcial.

Custo registrado com `record_chat_usage(operation="coverage")` — `services/usage/` já suporta
operação nova sem alteração (verificar em `services/usage/mappers.py` na execução).

**Endpoint** — `api/v1/cohorts.py`, ao lado de `transcribe_lesson_report`:

```
POST /cohorts/{cohort_id}/propose-coverage   (PROFESSOR)
  form: lesson_id, transcript
  → { segments: [...] }
```
Autorização pelo mesmo `_lesson_class_of_professor` — ponto único de autorização, já existente.
Falha na proposta **não bloqueia** o encerramento: o front cai no segmento padrão (âncora, full).

---

## Fase 3 — Persistência e consolidação

**`services/lesson_completion_service.py`**

- `complete_lesson(...)` ganha `coverage: list[CoverageSegmentIn] | None`. Persiste as linhas de
  `LessonCoverage` junto da nota, no mesmo flush. Sem cobertura informada → **uma linha default**
  `(âncora, planned, full, pending="")`: o caminho feliz continua idêntico ao de hoje, e clientes
  antigos não quebram.
- `consolidate_notes(...)` ganha a cobertura confirmada como entrada, e o
  `CONSOLIDATION_SYSTEM_PROMPT` passa a instruir que **`summary`, `unclear_points` e
  `knowledge_base` descrevem só o que a cobertura declara como ministrado** — o que fecha o
  vazamento do F0.3 na origem: o excedente não é mais dobrado no `knowledge_base` da âncora.
- `api/v1/cohorts.py` — `complete()` aceita `coverage` como campo JSON do form, valida que os
  `lesson_id` estão na janela de candidatas e que a âncora está presente. Guard de sequência
  **inalterado**.

**`services/student_progress_service.py`** — `close_by_advance` inalterado no comportamento;
apenas o assessment que ele enfileira passa a ver a cobertura (Fase 5). Ordem já garantida:
a cobertura é escrita antes do `enqueue_after_commit`.

---

## Fase 4 — Contexto da Lira

**`ai/context_builder.py`** — `ContextBundle` ganha:

```python
taught_scope: list[dict] = field(default_factory=list)
# [{"lesson": título, "covered": "...", "pending": "...", "origin": "planned|carryover|advance"}]
```

Em `to_system_blocks()`, entra como bloco próprio — **`## Escopo realmente ministrado`** —
antes do conteúdo planejado. `build_lesson` popula via `coverage_service.taught_scope_for`,
incluindo os segmentos `carryover` e `advance` da sessão da âncora.

**Regra estrutural preservada:** o segmento `advance` entra **só como texto `covered`** — a
descrição do que foi dito em sala. O `lesson.content` da aula futura continua fora do bundle,
e `unlocked` no `track_map` continua governado por `CohortProgress`. O aluno não ganha acesso
ao catálogo da aula seguinte; ganha acesso ao que ele de fato ouviu.

**`ai/engine.py`** — `SYSTEM_BASE`: a âncora das perguntas passa a ser o escopo ministrado, com
o `unlocked_content` como material de referência. Uma linha reescrita, não um bloco novo de regras.

**`services/playground_context_service.py:120`** — incluir `taught_scope` no payload, para o
admin inspecionar. Voz (`instructions_builder.py:177`) propaga sozinha.

---

## Fase 5 — Avaliação

**`services/assessment/lesson_assessment_service.py`**

- `_build_user_prompt` ganha `## Escopo realmente ministrado nesta aula` **antes** de
  `## Material da aula`, e o header do planejado passa a dizer explicitamente que é referência
  do plano, não escopo de cobrança.
- `_lesson_closure_block` ganha duas informações quando existem:
  - pendência vigente → "este conteúdo não foi ministrado ao aluno";
  - cauda coberta numa sessão posterior (carryover) → aponta que a evidência daquele conteúdo
    é colhida na conversa daquela sessão.

**`services/assessment/evaluator.py`** — `EVALUATOR_SYSTEM_PROMPT`: "a cobertura do escopo" passa
a se referir ao **escopo ministrado**. Conteúdo declarado como não ministrado sai da conta —
não é lacuna do aluno, é dado de operação. O resto do prompt (proibição de nota numérica,
julgamento livre, `level: null` válido) fica intacto.

Módulo e trilha (`module_assessment_service`, `track_assessment_service`) **não mudam**: leem os
filhos, que já vêm corrigidos.

---

## Fase 6 — Frontend

**`components/cohorts/LessonReportCapture.tsx`** — entre o relato e o submit:

```
Relato: "hoje fechei tom formal, que faltou na aula 1,
         e comecei coesão da aula 2"

Cobertura desta aula                          [ Ajustar ]
  Aula 1 · Tom formal      cauda fechada   ✔ pendência resolvida
  Aula 2 · Coesão          parcial         ⚠ falta coerência textual

[ Encerrar aula ]
```

Proposta chamada quando há transcript (após transcrição ou digitação, com debounce). "Ajustar"
abre a edição dos segmentos: extensão (full/partial), texto de coberto/pendente, e adicionar ou
remover aula da janela de candidatas. Segmento tocado → `source: "professor"`.

Estados a cobrir: proposta carregando, proposta falhou (segue com o default, aviso discreto),
sem transcript (default silencioso). O padrão de `useApiAction` + `AudioProcessStatus` já
existente cobre o feedback.

**`components/cohorts/CohortProgressPanel.tsx`** — aula com pendência vigente ganha marcador e o
texto do que falta. É o "delta como dado de operação" da seção 3 do doc, visível para o professor.

---

## Fase 7 — Verificação

**`bin/verify-dinamismo`** — no padrão da Fase 6 de `student_lesson_progression.plan.md`. Roda
sobre o seed (`bin/db-reset`) e imprime o que foi registrado em cada cenário:

| # | Cenário | Asserção |
|---|---|---|
| 1 | **Caminho felizf** (regressão) | Uma cobertura `(âncora, planned, full)`; bundle, dispatch e assessment idênticos ao pré-mudança |
| 2 | **Incompleta** | `pending` não vazio na âncora; `taught_scope` exclui o pendente; avaliador não cobra o pendente; `CohortProgress` criado (turma avançou) |
| 3 | **Adiantada** | Segmento `advance` na aula seguinte; `knowledge_base` da âncora **sem** o conteúdo adiantado; `lesson.content` da aula seguinte **fora** do bundle; sem segundo dispatch |
| 4 | **Composta** | Segmento `carryover` resolve a pendência da anterior; uma conversa só, na âncora; `taught_scope` traz os dois blocos com origem |
| 5 | **Pendência resolvida** | Após a sessão de carryover, `current_pendings` da aula anterior fica vazio |

Regressão adicional a checar na execução: voz (`instructions_builder`), playground admin,
roteamento inbound (`bin/send-message`) e turma com dois professores no mesmo módulo.

---

## Ajustes de desenho feitos na execução

Dois pontos que o plano não previa e a verificação expôs. Ambos apertam o desenho — não o alargam.

### A janela é limitada ao módulo da própria turma

O plano falava de "vizinhança da âncora" na trilha. Só que a vizinhança atravessa a fronteira
de módulo, e cada módulo tem sua própria `CohortModuleProfessor`. Sem o corte, um professor
poderia declarar cobertura sobre uma aula que **não ensina** — e a linha apareceria no painel
sob a turma dele, que é dado falso.

`candidate_window` passou a filtrar pelo módulo da turma âncora — o mesmo corte que
`MidJoinService.next_open_lesson_id` já usa para decidir o que uma turma pode encerrar. Efeito
colateral aceito e documentado: **adiantar através de uma fronteira de módulo não é
expressável**. Isso é correto, não uma limitação: adiantar para dentro do módulo de outro
professor não é desvio de uma turma, é mudança de plano entre dois professores.

### Uma pendência não expira quando a turma anda

O plano assumia que a cauda seria fechada na aula imediatamente seguinte. Mas se a turma
avançou duas aulas e só então o professor voltou para fechar o que faltou, a janela de
vizinhança já não alcançava aquela aula, e o `carryover` era descartado — a pendência ficaria
impossível de resolver, o oposto do que a seção 5 do doc pede.

`candidate_window` passou a incluir, além da vizinhança, **qualquer aula anterior do módulo que
ainda deva algo àquela turma**. A pendência vigente é o próprio sinal de que a aula continua
aberta para carryover.

---

## Trade-offs aceitos

1. **Avaliação da aula anterior num cenário composta.** `close_by_advance` enfileira o assessment
   da anterior no momento do encerramento, antes de a conversa da âncora acontecer. A linha de
   assessment daquela aula não carregará a evidência nova; ela é colhida na conversa da âncora e
   consta no assessment da âncora. Mitigação barata na Fase 5: o closure block da anterior aponta
   onde a evidência vive, então o avaliador reporta lacuna correta em vez de ausência falsa.
   Roteamento de evidência entre aulas fica fora — é máquina de estados nova, não é o pedido.
2. **Um pouco de texto no lugar de estrutura pura.** "Este conteúdo não foi ministrado" é uma
   frase no prompt. A alternativa estrutural seria recortar `lesson.content` pelo segmento, o que
   exigiria a IA fatiar o conteúdo planejado — heurística, justamente o que o projeto evita. O
   dado é estruturado (covered/pending em coluna); só a leitura é textual.
3. **Custo de uma chamada de IA por encerramento.** Modelo do `ENGINE_MODEL`, contexto pequeno
   (janela de 4 aulas + relato), registrada em `ai_usage_events` como as outras.

## Fora de escopo

Sequência de aulas, dispatch, roteamento inbound, invariante de uma ATIVA por aluno, divisão
multi-professor, avaliação de módulo/trilha, tenancy, custos, voz. Nenhum desses é tocado —
a Fase 7 os verifica como regressão.

## Ordem de execução

`1 → 2 → 3 → 4 → 5 → 6 → 7`. Backend inteiro antes do front, para a Fase 6 consumir endpoint real.

---

## Resultado

**`bin/verify-dinamismo` — 26/26 verificações; com `--with-ai`, 29/29.**

```
1 · Caminho feliz (regressão)      4/4   cobertura default, bundle idêntico ao pré-mudança
2 · Aula incompleta                6/6   pendência registrada, fora da cobrança, turma avança
3 · Aula composta                  3/3   carryover fecha a pendência, uma conversa na âncora
4 · Pendência resolvida            4/4   resolve sem UPDATE, histórico e evidência rastreados
5 · Aula adiantada                 7/7   excedente guardado, aula seguinte não liberada,
                                         conteúdo planejado dela continua fora do bundle
6 · Guardas                        2/2   segmento fora da janela descartado, âncora garantida
7 · Proposta pela IA               3/3   segmentação derivada do relato, dentro da janela
```

Também exercitado à mão sobre a API: `POST /propose-coverage` (a IA detectou aula incompleta a
partir do relato), `POST /complete-lesson` com a cobertura confirmada (pendência aparece em
`GET /progress`, que alimenta o painel), cobertura malformada → 400, e encerramento **sem**
cobertura → 200 com o comportamento anterior. `npm run build` (`tsc -b` + vite) limpo.
