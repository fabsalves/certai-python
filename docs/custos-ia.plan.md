# Custos de IA — plano de execução (CertAI)

Salvar em `docs/custos-ia.plan.md` no `certai-python`.
Base de estimativa (modelo teórico, sem medição): conversa de 20/08/2026.
**Referência de estrutura:** `/home/eriko/documentos/almai/prumo` — a tela
`Gastos` já resolve este problema em produção. Este plano porta a estrutura dela
e mantém 100% do layout, RBAC, filtros e paginação do CertAI.

**Projeto não está em produção.** Sem preocupação com dados existentes,
compatibilidade ou migração de histórico. Reestruturar livremente.

---

## 1. Objetivo

Hoje **nada é medido**. Não existe um único registro de token ou custo no código.
Toda estimativa de "quanto custa uma avaliação por aluno" é chute.

Construir a medição real e uma área própria — **Custos** — com o gasto
consolidado por **turma → aluno → aula**, na mesma granularidade das avaliações
por camadas (`docs/avaliacao-camadas.plan.md`).

O núcleo é **minuto de voz**. O Realtime (`gpt-realtime-2`) é ~90% da conta;
motor, humanizador, avaliador e ingestão são centavos.

---

## 2. O que vem do prumo, o que muda

### Adotar como está

| # | O quê | Onde no prumo |
|---|---|---|
| 1 | **Linha por `cost_kind`**, não coluna por modalidade | `models/__init__.py:232` |
| 2 | Idempotência por `(provider, provider_event_id, cost_kind)` + `on_conflict_do_nothing` | `services/usage/ingest.py` |
| 3 | **Custo congelado na ingestão** + `raw` JSONB da resposta | `services/usage/pricing.py` |
| 4 | Rate card com fallback por prefixo de família (`gpt-realtime-2*` → `gpt-realtime-2`) | `pricing.py:get_rate_usd_per_million` |
| 5 | **`mappers.py`** — normalização do payload real do Realtime | `services/usage/mappers.py` |
| 6 | Captura do usage da **transcrição de entrada** | `lib/realtime.ts:355` |
| 7 | **Fila com debounce + flush `keepalive`** no teardown | `lib/realtime.ts:504-537` |
| 8 | `COST_KIND_LABELS` + agregação pura em SQL | `services/usage/aggregate.py` |
| 9 | Breakdown "por tipo de gasto" em todo nível de drill-down | `pages/Usage.tsx:KindTable` |

O item 5 é o maior ganho: o `usage` do `response.done` vem em
`input_token_details.{text,audio,image}_tokens` + `cached_tokens_details` +
`output_token_details`, com fallback pra totais quando a API não manda o
breakdown. Isso é conhecimento que só se obtém batendo a cabeça — está pronto lá.

O item 7 elimina o risco que eu tinha declarado como perda aceitável: fila com
debounce de 400ms, `fetch(..., { keepalive: true })` no `stop()`, e requeue em
caso de falha. O último `response.done` não se perde.

### Adotar corrigindo

**`estimate_cost_usd` do prumo retorna `Decimal("0")` para modelo sem tarifa**
(`pricing.py:82`). Modelo não precificado aparece como **gratuito** — o pior
resultado possível numa tela de custo, porque é silencioso.

No CertAI: tarifa ausente grava `estimated_cost_usd = NULL`, e a linha entra no
contador `unpriced_events` de todo agregado. Lacuna declarada, nunca zero.

### Não adotar

| O quê | Por quê |
|---|---|
| **Paginação server-side** (`page`/`page_size`, offset/limit, count query) | O CertAI não tem esse precedente em nenhuma listagem. `/users`, `/cohorts` e `/tracks` retornam lista completa e a paginação é client-side (`usePagination`). Ver seção 8 |
| **Drill-down por `useState` view machine** (`{kind:"list"|"user"|"conversation"}`) | O CertAI usa rotas reais (`/tracks/:trackId`, `/cohorts/:cohortId` em `RoleRoute`). Botão "← Voltar" com estado interno quebra o back do navegador |
| Eixo **usuário → conversa** | O eixo do CertAI é **turma → aluno → aula**, o mesmo das avaliações por camadas |
| Classes CSS `usage__totals`, `usage__filters`, `usage__muted` | Já existem equivalentes: `page-grid--stats` + `stat-card`, `ListToolbar`, `muted` |

---

## 3. Decisões cravadas

| Tema | Decisão |
|---|---|
| Unidade de registro | **Uma linha por `cost_kind`** de cada evento do provedor (modelo do prumo) |
| Custo | **Congelado na ingestão**, com `raw` JSONB guardado. Atualizar a tabela de preços não reescreve histórico; o `raw` permite reprecificar se um dia precisar |
| Tarifa ausente | `estimated_cost_usd = NULL` + contador `unpriced_events`. **Nunca zero** |
| Escopo de cada linha | `cohort_id` + `student_id` + `lesson_id` (nullable) — mesma segregação do `ToolContext` |
| Agregação | **SQL `GROUP BY`**, nunca laço em Python |
| Paginação / filtros | **Client-side**, igual a todas as listagens. Agregado já vem reduzido do banco |
| RBAC | **Somente `admin`**, igual ao Playground |
| Navegação | Rotas reais, back do navegador funcionando |
| Moeda | Cálculo em **USD**. BRL é conversão de exibição (`settings.USD_BRL_RATE`) |
| Estimativa | **Proibida.** Aula sem medição é "sem dados", não projeção |

---

## 4. Pontos de captura

| # | Ponto | Arquivo | Peso |
|---|---|---|---|
| 1 | **Realtime `response.done`** | `frontend/src/realtime/RealtimeWebRTCClient.ts:301` | **~85%** |
| 2 | **Transcrição de entrada** (`input_audio_transcription.completed`) | `RealtimeWebRTCClient.ts:278` | ~5% |
| 3 | Motor (texto/WhatsApp) | `backend/app/ai/engine.py:respond` | médio |
| 4 | Humanizador | `backend/app/ai/humanizer.py:humanize` | baixo |
| 5 | Avaliador (aula/módulo/trilha) | `backend/app/services/assessment/evaluator.py` | baixo |
| 6 | Ingestão (relato + material) | `backend/app/services/ingestion/` | baixo |
| 7 | Resumo de histórico descartado | `instructions_builder.py:_summarize_dropped_turns` | raro |
| 8 | Transcrição do professor (Groq) | `backend/app/services/transcription_service.py` | baixo |

1 e 2 **não** passam pelo `AsyncOpenAI` do backend — a sessão é WebRTC direto do
browser. Os dois branches já existem no `RealtimeWebRTCClient` e hoje só fazem
`console.log`. Sem o relay, 90% do custo é invisível.

`app/ai/client.py` **não** vira wrapper de contabilidade — ele não conhece
`cohort_id`/`student_id`/`lesson_id`. Registro explícito em cada call site.

---

## 5. Modelo

`AiUsageEvent` em `backend/app/models/usage.py`. Herda `Base` (PK UUID + timestamps).
Estrutura do `UsageEvent` do prumo, com o escopo do CertAI.

```
cohort_id           FK cohorts.id   CASCADE, index, NOT NULL
student_id          FK users.id     CASCADE, index, nullable
lesson_id           FK lessons.id   SET NULL, index, nullable
provider            String(40)   NOT NULL      "openai" | "groq"
model               String(120)  NOT NULL      valor REAL da API, não o de settings
operation           String(60)   NOT NULL      "realtime_response" | "input_transcription"
                                               | "engine" | "humanizer" | "evaluator"
                                               | "ingestion" | "summarizer" | "transcription"
cost_kind           String(60)   NOT NULL      ver seção 6
quantity            Numeric(18,6) NOT NULL
unit                String(20)   NOT NULL, default "tokens"
estimated_cost_usd  Numeric(12,6) NULLABLE     NULL = sem tarifa conhecida
provider_event_id   String(120)  NOT NULL      response_id / event_id
raw                 JSONB        nullable      payload cru, para reprecificar
occurred_at         DateTime(tz) NOT NULL
```

```
UniqueConstraint(provider, provider_event_id, cost_kind,
                 name="uq_ai_usage_events_provider_event_kind")
Index("ix_ai_usage_events_cohort_occurred", cohort_id, occurred_at.desc())
Index("ix_ai_usage_events_cohort_student_lesson", cohort_id, student_id, lesson_id)
Index("ix_ai_usage_events_kind", provider, cost_kind)
```

**Por que linha por `cost_kind` e não coluna por modalidade:** o preço difere ~8x
entre texto e áudio e ~80x entre áudio fresco e cacheado. Modalidade nova (imagem,
imagem em cache) é uma string nova, não uma migration. E `GROUP BY cost_kind`
entrega o breakdown de graça — que é a informação que responde *por que* custou.

Migration: `backend/alembic/versions/017_ai_usage_events.py`,
`down_revision = "016_module_description"`.

---

## 6. `cost_kind` e tabela de preços

`backend/app/services/usage/pricing.py` — port do prumo. USD por 1M de tokens,
dict literal versionado em código. Sem ENV, sem banco.

```
realtime_audio_in           32.00     realtime_audio_in_cached      0.40
realtime_audio_out          64.00     realtime_text_in_cached       0.40
realtime_text_in             4.00     realtime_image_in             5.00
realtime_text_out           24.00     realtime_image_in_cached      0.50
transcribe_audio_in          5.00     transcribe_text_in            0.60
transcribe_text_out          0.60
chat_text_in / _out / _cached_in         por modelo (gpt-4o, gpt-4o-mini)
```

Fallback por prefixo de família, igual ao prumo: `gpt-realtime-2.1` cai em
`gpt-realtime-2` se não tiver entrada própria. Sem tarifa → `None`, **nunca 0**.

`settings.USD_BRL_RATE: float = 5.50` — só exibição.

> Números portados do prumo, que roda com eles. `realtime_text_out` lá é
> **$24/1M** (eu tinha estimado $16). **Conferir na página de pricing da OpenAI
> antes de expor número externamente** — é a única parte do plano não verificada.

---

## 7. Serviços

```
backend/app/services/usage/
  __init__.py       # re-exports, no padrão do prumo
  pricing.py        # rate card + estimate_cost_usd -> Decimal | None
  mappers.py        # payload do provedor -> list[UsageLine]   (port direto)
  ingest.py         # ingest_usage_batch(...) idempotente
  read_service.py   # agregação SQL — nome do CertAI, não "aggregate.py"
```

`mappers.py` e `ingest.py` são port quase literal do prumo. `ingest.py` ganha o
escopo do CertAI (`cohort_id`/`student_id`/`lesson_id`) e passa a gravar `None`
em vez de `0` quando não há tarifa.

`read_service.py` segue o padrão de `app/services/assessment/read_service.py` —
dataclasses frozen + `GROUP BY`, zero IA:

```python
@dataclass(frozen=True)
class CohortCostRow:
    cohort_id: uuid.UUID
    cohort_title: str
    track_title: str
    student_count: int
    lesson_count: int              # aulas COM medição
    voice_minutes_est: float
    cost_usd: Decimal
    cost_per_student_usd: Decimal
    cost_per_lesson_usd: Decimal
    unpriced_events: int

@dataclass(frozen=True)
class KindBreakdownRow:            # do prumo — vale em todo nível
    cost_kind: str
    label: str
    provider: str
    total_tokens: Decimal
    cost_usd: Decimal | None

@dataclass(frozen=True)
class StudentCostRow:
    student_id: uuid.UUID
    student_name: str
    voice_minutes_est: float
    cost_usd: Decimal
    cost_per_lesson_usd: Decimal

@dataclass(frozen=True)
class LessonCostRow:
    lesson_id: uuid.UUID
    lesson_title: str
    module_title: str
    voice_minutes_est: float
    voice_cost_usd: Decimal
    other_cost_usd: Decimal
    cost_usd: Decimal
```

`voice_minutes_est` = (`realtime_audio_in` + `realtime_audio_out` + cacheados) ÷ 10 ÷ 60.
Áudio ≈ 10 tokens/segundo — aproximação da OpenAI, não relógio. O sufixo `_est`
fica no nome até a tela, de propósito.

`COST_KIND_LABELS` em pt-BR, port do prumo, com as entradas de chat adicionadas.

---

## 8. API

`backend/app/api/v1/costs.py`, registrado em `router.py`.

```python
router = APIRouter(prefix="/costs", tags=["costs"])
can_view_costs = require_roles(Role.ADMIN)
```

| Rota | Retorno |
|---|---|
| `GET /costs/cohorts` | `list[CohortCostOut]` — uma linha por turma |
| `GET /costs/cohorts/{cohort_id}` | `CohortCostDetailOut` — totais + `by_kind` + `list[StudentCostOut]` |
| `GET /costs/cohorts/{cohort_id}/students/{student_id}` | `StudentCostDetailOut` — totais + `by_kind` + `list[LessonCostOut]` |
| `POST /realtime/usage` | relay do usage da voz (em `realtime.py`) |

Filtro de período por `Query` (`from`/`to`, default últimos 30 dias, igual ao
`_usage_window` do prumo) — período é filtro de **banco**, não de tela: não dá
pra filtrar client-side o que não veio.

**Sem `Query` de paginação.** Retorna lista completa, igual a `/users` e
`/cohorts`. O agregado já vem reduzido pelo `GROUP BY`: o volume é o número de
turmas, de alunos por turma e de aulas por aluno — dezenas, não milhares.

**A lista de eventos crus do prumo não entra no v1.** É o único nível
verdadeiramente ilimitado, e é o que forçaria paginação server-side — um
paradigma que o CertAI não tem em nenhuma tela. O breakdown por `cost_kind`
responde a mesma pergunta ("onde foi o dinheiro") sem o custo arquitetural.
Se um dia precisar do evento cru: o `Pagination` do CertAI é presentacional
(recebe `page`/`totalPages`/`total`/`from`/`to`), então o adaptador `ServerPager`
do prumo (`pages/Usage.tsx:290`) resolve sem tocar no componente.

**`POST /realtime/usage`** segue o contrato de `/realtime/turns` — `voice_session_id`
+ `lock_token` + `items`, validando o lock pelo `_voice_session_service` e
traduzindo `VoiceSessionLockInvalid` por `_lock_http_error`. Escopo resolvido
server-side a partir da `VoiceSession` (mesmo caminho de `_load_session_context`):
o browser nunca informa `cohort_id`/`student_id`/`lesson_id`.

```python
class RealtimeUsageItemIn(BaseModel):
    provider: str = "openai"
    model: str
    operation: str              # "realtime_response" | "input_transcription"
    provider_event_id: str
    usage: dict
    occurred_at: datetime | None = None

class RealtimeUsageIn(BaseModel):
    voice_session_id: uuid.UUID
    lock_token: str
    items: list[RealtimeUsageItemIn]
```

Schemas de saída em `app/schemas/__init__.py`: `CohortCostOut`,
`CohortCostDetailOut`, `StudentCostOut`, `StudentCostDetailOut`, `LessonCostOut`,
`KindBreakdownOut`.

---

## 9. Frontend

### Menu e rotas

- `lib/access.ts`: `costs: ["admin"] as Role[]`
- `components/layout/nav.ts`: `{ to: "/costs", label: "Custos", description: "Consumo de IA por turma e aluno", roles: ACCESS.costs, icon: "costs" }`, depois do Playground
- `components/layout/NavIcon.tsx`: chave `costs` no dict `icons` — stroke simples, sem fill
- `App.tsx`, dentro do `AppShell`, todas em `RoleRoute area="costs"`:
  - `/costs` → `Costs`
  - `/costs/:cohortId` → `CohortCosts`
  - `/costs/:cohortId/alunos/:studentId` → `StudentCosts`

Três rotas reais em vez da view machine do prumo. Back do navegador, link
compartilhável, `RoleRoute` em cada nível.

### Telas

Referência canônica de listagem: `pages/Professors.tsx`. Nenhum componente novo
onde já existe um em `components/ui/`.

**`pages/Costs.tsx`** — turmas.
`useListView("costs")` + `ViewToggle` · `PageHeader` ("Custos" / "Consumo de IA
medido por turma, aluno e aula.") · faixa `page-grid page-grid--stats` com
`card stat-card` (total do período, custo médio por aluno, custo médio por aula) ·
`ListToolbar` com busca `matchesAnySearch` em turma/trilha + `ListFilterSelect`
de trilha + `ListFilterSelect` de período (30/90 dias, tudo) ·
`DataTable`: Turma (`primary`) · Trilha · Alunos · Min. de voz (est.) ·
Custo/aluno · Custo total · ações (`card: "actions"`, `align: "end"`, "Detalhar") ·
`Pagination` com `usePagination(filtered, { resetKey: search })` ·
`ListEmptyFilter` ao filtrar a zero · `card empty-state` sem medição alguma ·
`CostsListSkeleton` em `components/costs/`, reusando `ListTableSkeleton`.

**`pages/CohortCosts.tsx`** — `/costs/:cohortId`, alunos da turma.
`PageHeader` com `eyebrow` = nome da turma · faixa de `stat-card` · **`KindBreakdown`**
(o `KindTable` do prumo, em `components/costs/`) · `ListToolbar` com busca por
aluno · `DataTable`: Aluno (`primary`) · Min. de voz (est.) · Custo/aula ·
Custo total · "Detalhar" · `Pagination`.

**`pages/StudentCosts.tsx`** — `/costs/:cohortId/alunos/:studentId`, aulas do aluno.
Mesma estrutura · `DataTable`: Aula (`primary`) · Módulo · Min. de voz (est.) ·
Voz · Outros · Total · `FilterSegment` "Todas" / "Só com medição".

**`components/costs/KindBreakdown.tsx`** — port do `KindTable`, usando o
`DataTable` do CertAI: Tipo (`primary`) · Provedor · Tokens · USD. Aparece nos
três níveis, igual ao prumo. É a tela que responde *por que* custou.

**`lib/costs.ts`** — tipos + chamadas `api.get`, no padrão de `lib/assessments.ts`.
Helpers `formatUsd`, `formatBrl`, `formatTokens`, `formatMinutes` aqui.
Nenhum `Intl` solto nas telas (o CertAI hoje não tem nenhum helper de formatação —
este arquivo passa a ser o lugar).

### Responsividade

Vem de graça e é obrigatório verificar, não presumir:

- `DataTable` já entrega tabela no desktop e **cards empilhados com campos
  rotulados no mobile** — daí a marcação `primary` / `card: "actions"` em toda
  coluna. Coluna sem papel de card definido vira campo rotulado; coluna de ação
  precisa de `card: "actions"` senão vira uma linha `dt/dd` feia no celular.
- `page-grid--stats` já é `repeat(auto-fit, minmax(200px, 1fr))` e vira 3 colunas
  no breakpoint (`shell.css:443` e `:4514`). Não criar grid novo.
- `ViewToggle` só faz sentido no desktop — no mobile o `DataTable` já força cards.
  Renderizar só quando há dados, igual ao `Professors.tsx`.
- Números longos (`US$ 1.234,56`, `12.345.678 tokens`) são o risco real de
  overflow no card. Testar em 360px de largura.
- Tema claro/escuro: usar só tokens de cor já definidos. Nada de hex novo.

### Regra de exibição

**Valor não medido renderiza `—` com `className="muted"`. Nunca `US$ 0,00`.**
Zero é uma afirmação; `—` é a verdade. Quando `unpriced_events > 0`, a tela
mostra o aviso — o custo exibido está **incompleto**, e esconder isso é pior que
não ter a tela.

---

## 10. Fases

Uma fase por vez, com teste antes de avançar.

- **Fase 1** — `AiUsageEvent` + migration `017` + `pricing.py` + `mappers.py` + `ingest.py`
- **Fase 2** — `POST /realtime/usage` + relay com fila/`keepalive` no frontend. **É a fase que importa**
- **Fase 3** — Instrumentar o backend (motor, humanizador, avaliador, ingestão, summarizer, Groq)
- **Fase 4** — `read_service.py` + `api/v1/costs.py` + schemas
- **Fase 5** — Menu, rotas, três telas, `KindBreakdown`, skeleton

Voz subiu de Fase 3 pra **Fase 2**: é 90% do custo e não depende das outras
capturas. Com as Fases 1–2 o chute da conversa anterior já virou medição, antes
de existir qualquer tela.

---

## 11. Riscos declarados

| Risco | Realidade |
|---|---|
| Preço de `gpt-realtime-2` não confirmado | Portado do prumo, que roda com ele. Único número não verificado do plano. Conferir na OpenAI antes de expor externamente |
| Usage da voz vem do browser | Mitigado pela fila com `keepalive` do prumo. Resta perda em crash duro do browser — aceitável |
| Custo congelado na ingestão | Tarifa errada contamina o histórico. Mitigado pelo `raw` JSONB: dá pra reprecificar rodando o `mappers` + `pricing` de novo sobre as linhas |
| `ai_usage_events` cresce rápido | ~6-8 linhas por turno de voz. Turma de 30 alunos × 11 aulas × 20 turnos ≈ 50k linhas. Irrelevante hoje; tabela agregada só quando doer |
| Paginação client-side | Correta pro agregado. Se a lista por aluno passar de alguns milhares, usar o adaptador `ServerPager` do prumo sobre o `Pagination` existente |
| Minutos de voz derivados de token | ~10 tokens/s é aproximação. Nome `_est` mantido até a coluna da tela |

---

## 12. Implementado — desvios do plano

Todas as 5 fases estão implementadas e validadas. Quatro decisões mudaram
durante a execução, por motivos descobertos no código:

**1. `cohort_id` é NULLABLE.** Ingestão de material de trilha pertence a uma
`Track`, que serve várias turmas — não há turma para cobrar. Com `NOT NULL` esse
gasto real ficaria fora da conta. Agora essas linhas entram como *overhead não
atribuído*, somam no total geral e aparecem num `stat-card` próprio, sem inflar o
custo/aluno de nenhuma turma.

**2. `cost_per_lesson_usd` da turma virou `cost_per_student_lesson_usd`.**
`total / aulas` mistura todos os alunos e superestima pelo tamanho da turma. O
denominador correto é o número de pares `(aluno, aula)` distintos com medição —
que é literalmente "quanto custa uma avaliação por aluno".

**3. Bug de dupla subtração no `mappers.py` do prumo.** Quando a API não manda o
breakdown por modalidade, o prumo faz `text_in = total - cached` e depois subtrai
`cached` outra vez no `add()`, zerando a linha de tokens frescos. Corrigido aqui:
`text_in` fica bruto e a subtração acontece uma única vez. Vale reportar no prumo.

**4. `humanize()`, `consolidate_notes()`, `build_track_guide()` e
`transcribe_audio()` receberam `db`/`scope` keyword-only OPCIONAIS.** Sem escopo,
a chamada simplesmente não é medida — nunca atribuída a um palpite. Playground e
importação de conteúdo de aula caem nesse caso.

### Validado

| O quê | Resultado |
|---|---|
| Migration `017` | sobe e desce limpa |
| 1 turno de voz (payload real do Realtime) | 8 linhas, US$ 0,0494 |
| Subtração de cache | `text_in` 6800−6200=600, `audio_in` 600−300=300 |
| Idempotência | replay do mesmo `response.done` → 0 linhas |
| Modelo sem tarifa | `estimated_cost_usd = NULL`, nunca 0 |
| Fallback de família | `gpt-4o-2024-11-20` precifica como `gpt-4o`; `gpt-4o-mini` não é sombreado |
| `POST /realtime/usage` | 200/8 linhas · replay 0 · lock inválido 409 · sessão inexistente 409 · lote vazio 200/0 |
| Escopo da voz | resolvido pela `VoiceSession`; o browser não informa turma/aluno/aula |
| RBAC | admin 200 · designer 403 · professor 403 · anônimo 401 |
| Agregação (2 alunos × 2 aulas × 12 turnos) | US$ 2,4656 · US$ 0,6164 por aluno-aula · voz = 93,8% |
| `tsc -b` + `vite build` | limpos |

O número que a área existe para responder, medido de ponta a ponta:
**voz é 93–96% do custo por aluno.**

---

## Prompt — Fase 1 (persistência e precificação)

```
FASE 1 de 5: persistência e precificação do consumo de IA. Projeto certai-python
(entre em certai-python primeiro; não confundir com cert-ai). NÃO está em produção.
Contexto completo: docs/custos-ia.plan.md.

REFERÊNCIA DE ESTRUTURA: /home/eriko/documentos/almai/prumo — LEIA
backend/app/models/__init__.py (classe UsageEvent), backend/app/services/usage/
(pricing.py, mappers.py, ingest.py) e backend/alembic/versions/002_usage_events.py
ANTES de escrever qualquer linha. mappers.py e ingest.py são port quase literal.

Não instrumentar call sites, não criar endpoint, não mexer no frontend nesta fase.

CRIAR backend/app/models/usage.py com AiUsageEvent (tabela ai_usage_events),
campos, unique constraint e índices exatamente como na seção 5 do plano. Herdar
Base. Registrar em app/models/__init__.py.

CRIAR a migration backend/alembic/versions/017_ai_usage_events.py,
down_revision = "016_module_description", no estilo de 012_student_assessments.py.

CRIAR backend/app/services/usage/pricing.py — port do prumo: rate card por
provider/model/cost_kind, fallback por prefixo de família, estimate_cost_usd().
DIFERENÇA OBRIGATÓRIA vs prumo: tarifa desconhecida retorna None, NUNCA
Decimal("0"). O prumo tem esse bug em pricing.py:82 e ele faz modelo não
precificado parecer gratuito. Adicionar os cost_kind de chat (chat_text_in,
chat_text_out, chat_text_cached_in) para gpt-4o e gpt-4o-mini.

CRIAR backend/app/services/usage/mappers.py — port de prumo/.../mappers.py:
UsageLine + map_openai_realtime_response + map_openai_transcription, com os
mesmos fallbacks (breakdown de modalidade quando existe, totais quando não).
ADICIONAR map_openai_chat_completion para o usage do Chat Completions
(prompt_tokens_details.cached_tokens → chat_text_cached_in).

CRIAR backend/app/services/usage/ingest.py — port de prumo/.../ingest.py, com o
escopo do CertAI (cohort_id, student_id, lesson_id) em vez de user_id/
conversation_id, gravando estimated_cost_usd=None quando pricing retorna None, e
on_conflict_do_nothing no constraint uq_ai_usage_events_provider_event_kind.
NUNCA propagar exceção pra fora: falha de contabilidade não pode derrubar uma aula.

ADICIONAR settings.USD_BRL_RATE: float = 5.50 em app/core/config.py e em .env.example.

Rodar a migration e confirmar que a tabela sobe limpa.
```

## Prompt — Fase 2 (voz — a fase que importa)

```
FASE 2 de 5: capturar o usage do Realtime. Contexto: docs/custos-ia.plan.md,
seções 4 e 8. Fase 1 concluída. Ainda sem telas.

REFERÊNCIA: /home/eriko/documentos/almai/prumo — LEIA
frontend/src/lib/realtime.ts (branches "response.done" e
"conversation.item.input_audio_transcription.completed", e os métodos
enqueueUsage/flushUsage/stop) e backend/app/api/v1/realtime.py (POST /usage).

BACKEND — em app/api/v1/realtime.py, criar POST /realtime/usage no contrato de
/realtime/turns: RealtimeUsageIn (voice_session_id, lock_token, items) validando
o lock pelo _voice_session_service e traduzindo VoiceSessionLockInvalid via
_lock_http_error. Resolver cohort_id/student_id/lesson_id SERVER-SIDE a partir da
VoiceSession (mesmo caminho de _load_session_context) — o browser NUNCA informa
escopo. Persistir via ingest_usage_batch. Response repetido é no-op silencioso
pelo unique, não erro. Schemas em app/schemas/__init__.py.

FRONTEND — em frontend/src/realtime/RealtimeWebRTCClient.ts:
- No branch type === "response.done" (hoje só console.log em ~:323), extrair
  payload.response.usage e enfileirar com operation "realtime_response",
  provider_event_id = event_id ?? response.id, model = o modelo da sessão.
- No branch "conversation.item.input_audio_transcription.completed" (~:278),
  extrair payload.usage e enfileirar com operation "input_transcription" e o
  modelo de transcrição da sessão. ESTE PONTO É FÁCIL DE ESQUECER — a transcrição
  de entrada é cobrada à parte e emite usage próprio.
- Implementar a fila do prumo: enqueueUsage com debounce de 400ms, flushUsage
  postando o lote, requeue via unshift em caso de falha, e flushUsage(keepalive)
  com fetch(..., { keepalive: true }) no teardown da sessão, para o último
  response.done não se perder quando o aluno fecha a aba.
- Dedup local por provider_event_id, no padrão do relayedStudentKeys já existente.
- Falha de relay NUNCA interrompe a call: try/catch e segue.

VALIDAR com uma call real de ponta a ponta. Confirmar no banco linhas com
cost_kind realtime_audio_in / realtime_audio_out / realtime_audio_in_cached /
realtime_text_in_cached preenchidos, e linhas transcribe_*. Fechar a aba no meio
da call e confirmar que o último evento chegou. Comparar o custo total com a
estimativa de ~US$0,05/minuto de conversa — divergência grande indica erro na
tabela de preços ou no mapper, não na medição.
```

## Prompt — Fase 3 (instrumentar o backend)

```
FASE 3 de 5: instrumentar os call sites de LLM do backend. Contexto:
docs/custos-ia.plan.md, seção 4. Fases 1-2 concluídas. Sem endpoint novo, sem frontend.

Chamar ingest_usage_batch() (ou um helper fino sobre ele) em cada ponto, passando
o escopo de quem chama e usando map_openai_chat_completion:

- app/ai/engine.py:respond — uma vez por chamada da API dentro do loop.
  operation="engine". Escopo vem do ToolContext (cohort_id, student_id,
  lesson_id) — passar o ToolContext ou seus ids para respond().
- app/ai/humanizer.py:humanize — operation="humanizer". humanize() hoje não
  conhece escopo: adicionar parâmetros keyword-only opcionais e repassar de quem
  chama. Sem escopo, gravar student_id/lesson_id nulos — nunca inventar.
- app/services/assessment/evaluator.py — operation="evaluator".
- app/services/ingestion/ — operation="ingestion".
- app/services/realtime/instructions_builder.py:_summarize_dropped_turns —
  operation="summarizer".
- app/services/transcription_service.py — operation="transcription",
  provider="groq", cost_kind por duração (unit="seconds").

provider_event_id: usar resp.id do Chat Completions. model: sempre o valor REAL
retornado pela API (resp.model), nunca o de settings.

VALIDAR com backend/scripts/verify_lesson_assessment.py e verify_integrated.py,
conferindo no banco que há linha por chamada com texto e cache separados.
```

## Prompt — Fase 4 (leitura e API)

```
FASE 4 de 5: agregação e endpoints. Contexto: docs/custos-ia.plan.md, seções 7 e 8.
Fases 1-3 concluídas, com dados reais. Sem frontend nesta fase.

REFERÊNCIA: /home/eriko/documentos/almai/prumo/backend/app/services/usage/aggregate.py
— LEIA antes: COST_KIND_LABELS, o padrão de _period_filter e as queries com
GROUP BY. Adotar a estrutura; trocar o eixo usuário→conversa pelo eixo
turma→aluno→aula.

CRIAR backend/app/services/usage/read_service.py (nome do CertAI, não
"aggregate.py") no padrão de app/services/assessment/read_service.py: dataclasses
frozen (CohortCostRow, StudentCostRow, LessonCostRow, KindBreakdownRow) e queries
SQL com GROUP BY. Nenhum laço em Python somando linha por linha, nenhuma IA.
COST_KIND_LABELS em pt-BR, port do prumo + entradas de chat.

Linha com estimated_cost_usd NULL entra em unpriced_events e NÃO soma ao custo.
voice_minutes_est = soma dos cost_kind de áudio do Realtime / 10 / 60, exposto
com o sufixo _est no schema.

CRIAR backend/app/api/v1/costs.py com prefix="/costs", can_view_costs =
require_roles(Role.ADMIN), e as três rotas GET da seção 8. Filtro de período por
Query from/to com default de 30 dias (padrão _usage_window do prumo). SEM Query
de paginação — lista completa, igual a /users. NÃO expor lista de eventos crus.
Registrar em app/api/v1/router.py. Schemas em app/schemas/__init__.py.

VALIDAR: chamar as três rotas e conferir que custo/aluno e custo/aula fecham com
a soma das linhas de ai_usage_events, e que unpriced_events aparece quando há
modelo fora do rate card.
```

## Prompt — Fase 5 (telas)

```
FASE 5 de 5: área Custos na plataforma. Contexto: docs/custos-ia.plan.md, seção 9.
Fases 1-4 concluídas.

PADRÃO: seguir o CertAI à risca. A referência canônica de listagem é
frontend/src/pages/Professors.tsx — ler antes de começar. NÃO inventar componente
onde já existe um em components/ui/ (DataTable, ListToolbar, ListFilterSelect,
FilterSegment, Pagination, ViewToggle, ListTableSkeleton, ListEmptyFilter).

INSPIRAÇÃO de conteúdo (NÃO de estrutura de navegação):
/home/eriko/documentos/almai/prumo/frontend/src/pages/Usage.tsx — ler o KindTable
(breakdown por tipo de gasto) e as colunas das tabelas. IGNORAR a view machine
por useState e o botão "← Voltar": o CertAI usa rotas reais.

MENU E ROTAS
- lib/access.ts: costs: ["admin"] as Role[]
- components/layout/nav.ts: "Custos", to "/costs", icon "costs",
  description "Consumo de IA por turma e aluno", depois do Playground
- components/layout/NavIcon.tsx: chave "costs" no dict icons — stroke simples, sem fill
- App.tsx, no AppShell, cada uma em RoleRoute area="costs":
  /costs, /costs/:cohortId, /costs/:cohortId/alunos/:studentId

lib/costs.ts: tipos espelhando os schemas, chamadas api.get no padrão de
lib/assessments.ts, e os helpers formatUsd/formatBrl/formatTokens/formatMinutes.
Nenhum Intl solto nas telas.

TELAS (colunas e composição na seção 9 do plano)
- pages/Costs.tsx (turmas), pages/CohortCosts.tsx (alunos),
  pages/StudentCosts.tsx (aulas)
- components/costs/KindBreakdown.tsx — port do KindTable do prumo sobre o
  DataTable do CertAI. Aparece nos três níveis
- components/costs/CostsListSkeleton.tsx reusando ListTableSkeleton

RESPONSIVIDADE — verificar, não presumir:
- Toda coluna precisa de papel de card explícito: primary na identificadora,
  card:"actions" + align:"end" na de ações. Senão o mobile fica quebrado
- Reusar page-grid page-grid--stats + card stat-card (já responsivo,
  shell.css:443 e :4514). Não criar grid novo
- Testar em 360px: valores monetários e contagens de token longos são o risco
  real de overflow no card
- Tema claro/escuro: só tokens de cor existentes, nenhum hex novo
- ViewToggle apenas quando há dados, igual ao Professors.tsx

REGRA DE EXIBIÇÃO: valor não medido é "—" com className="muted", NUNCA
US$ 0,00. E quando unpriced_events > 0, avisar na tela que o total está
incompleto.
```

---

## Fora deste card

Escopo deixado de fora de propósito (baixo impacto em $). Referência rápida
também no card do Trello #17.

| Path | Arquivo | Motivo |
|---|---|---|
| Playground `transcribe-report` | `backend/app/api/v1/admin/playground.py` | Chama Groq sem `db`/`scope`/`usage_event_id` |
| Import de áudio → conteúdo de aula | `backend/app/services/ingestion/lesson_content_import_service.py` | Groq sem metering |
| Fallback Groq `json` (sem duration) | `transcription_service.py` | Sem duração não dá pra precificar |

Produção (voz, chat/WhatsApp, humanizer, avaliador, ingestão de relato,
summarizer, Groq do professor) está instrumentada.
