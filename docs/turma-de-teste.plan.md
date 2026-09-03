---
name: Turma de Teste
overview: Uma turma pode ser marcada como turma de teste na criação — marca imutável. Nela, e só nela, o admin pode desfazer o último encerramento de aula ou zerar o andamento inteiro, rodando o fluxo real quantas vezes quiser em produção sem tocar em turma real. Cadastro e custos sobrevivem; andamento zera.
todos:
  - id: fase-1-marca
    content: "Fase 1: Cohort.is_sandbox + migration 020 + schemas (ausente no update = imutável)"
    status: completed
  - id: fase-2-servico
    content: "Fase 2: sandbox_service — desfazer último encerramento e zerar andamento, recusando turma real"
    status: completed
  - id: fase-3-endpoints
    content: "Fase 3: dois endpoints ORG_ADMIN sob /cohorts/{id}/sandbox/"
    status: completed
  - id: fase-4-frontend
    content: "Fase 4: badge Teste, checkbox na criação, dois botões no Andamento com confirmação danger"
    status: completed
  - id: fase-5-verificacao
    content: "Fase 5: bin/verify-sandbox — recusa em turma real, undo restaura pendência, reset preserva cadastro"
    status: completed
isProject: false
---

# Plano: Turma de Teste

**Projeto:** `certai-python` · branch `feat-dinamismo-aulas`
**Referências:** [`dinamismo-aulas.plan.md`](dinamismo-aulas.plan.md), [`../README.md`](../README.md)

**Necessidade:** o time precisa testar o ciclo de encerramento em **produção**, várias vezes,
sem pedir reset de banco e sem refazer o fluxo do zero — e sem risco para turma real.

**Premissa que dispensa metade do trabalho:** a progressão do CertAI já é por turma
(`CohortProgress`, `StudentLessonProgress`, notas, cobertura, conversas — tudo em `cohort_id`).
Encerrar aula na turma X nunca toca a turma Y. **O isolamento já existe.** O que falta é
repetibilidade: trazer *uma* turma de volta.

**Decisões (do Ériko):** marca na turma · WhatsApp dispara de verdade · custos preservados ·
somente `ORG_ADMIN` (papel designer foi descontinuado).

---

## O desenho em uma frase

**O cadastro fica. O andamento zera.**

| Sobrevive | Zera |
|---|---|
| `Cohort`, `Enrollment` | `CohortProgress` |
| `CohortModuleProfessor`, `CohortModuleStudent` | `CohortLessonNote` → `LessonCoverage` (cascade) |
| `Track` / `Module` / `Lesson` — os reais | `StudentLessonProgress` |
| `AiUsageEvent` — o gasto aconteceu | `Conversation` → `Message`, `VoiceSession` (cascade) |
| | `MicroScore`, `StudentAssessment` |

Depois de zerar, a turma volta a "aula 1 ainda não encerrada" e o ciclo roda de novo pelo
**mesmo** `complete_lesson`, mesmo motor, mesmos prompts. Não existe caminho paralelo de teste.

## Duas ações, uma primitiva e um atalho

| Ação | Uso |
|---|---|
| **Desfazer último encerramento** | O loop do testador: achou bug, o dev corrigiu e subiu, ele refaz só aquele passo. Aplicado em sequência, caminha para trás. |
| **Zerar andamento** | O fallback: quando o desfazer não deu conta, ou quando se quer começar do zero. |

O desfazer age sempre sobre **o encerramento mais recente da turma** — sem parâmetro, um botão.
Encerramento arbitrário no meio seria ambíguo; o mais recente não é. A resposta diz qual aula e
qual professor foram desfeitos.

## A garantia de segurança é estrutural

A marca de teste é definida **na criação e nunca pode ser alterada**. Não por uma validação que
alguém possa contornar: `is_sandbox` simplesmente **não existe em `CohortUpdate`**. Não há
contrato por onde mudá-la. Restrição vira estrutura, como no resto do projeto.

Consequência: **uma turma real criada sem a marca é permanentemente não-zerável** — não há
caminho, nem admin, nem `force`. O resto é reforço:

- os dois endpoints recusam turma sem a marca (400), sem override;
- `require_roles(Role.ORG_ADMIN)`, mesmo nível que já cria turma;
- confirmação `tone: "danger"` na UI, dizendo o que será apagado;
- log da ação com quem executou, qual turma e o que foi removido.

## Limitações honestas (entram na explicação para o time)

1. **A mensagem do WhatsApp já enviada não volta.** Apagar a conversa no banco não desenvia o
   template do celular. O testador fica com um convite velho no histórico — inofensivo, mas
   precisa estar dito, senão parece bug.
2. **Se a ingestão do relato estiver em andamento**, a task vai procurar uma nota apagada e
   falhar no log do worker. Nenhum efeito é aplicado; é ruído. Preferimos isso a bloquear o
   testador esperando processamento.
3. **Nunca matricular aluno real numa turma de teste** — ele receberia WhatsApp de teste. Regra
   de operação, não de código.

---

## Fase 1 — A marca

**`models/cohort.py`** — `Cohort.is_sandbox: bool` (default `False`, `nullable=False`), com
docstring explicando que a imutabilidade vem da ausência no contrato de update.

**`alembic/versions/020_cohort_sandbox.py`** — aditiva, `server_default="false"`.

**`schemas/__init__.py`**
- `CohortCreate.is_sandbox: bool = False` — entra só aqui;
- `CohortUpdate` — **não recebe o campo**. É a garantia;
- `CohortOut` expõe (a UI precisa para o badge e os botões).

## Fase 2 — `services/cohort/sandbox_service.py`

Arquivo em `services/cohort/`, junto de `mid_join_service.py` e `module_class_service.py`.

```python
class SandboxOnlyError(Exception): ...   # turma real: recusa, sem override

class SandboxService:
    @staticmethod
    async def undo_last_closure(db, cohort) -> dict   # {lesson_title, professor_name, removed}
    @staticmethod
    async def reset_progress(db, cohort) -> dict      # {removed: {...}}
```

Ambos começam com o mesmo guard: `if not cohort.is_sandbox: raise SandboxOnlyError`.

**`undo_last_closure`** — a nota mais recente da turma define o alvo:
1. apaga a `CohortLessonNote` → `LessonCoverage` vai por cascade;
2. apaga o `CohortProgress` daquela aula + turma de professor;
3. apaga `StudentLessonProgress`, `Conversation` (cascade), `MicroScore` e `StudentAssessment`
   daquela aula, para os alunos daquela turma de professor;
4. devolve a aula **anterior** de `ENCERRADA_POR_AVANCO` ao status que ela tinha, derivado sem
   adivinhação: `activated_at` preenchido → `ATIVA`, senão → `DISPARADA`; limpa
   `encerrada_por_avanco_at`.

> **A pendência volta sozinha.** Como a cobertura é append-only e amarrada ao `note_id` com
> cascade, apagar a nota faz a cobertura vigente da aula anterior voltar a ser a linha antiga —
> com a pendência original. Não há nada a "restaurar": a ausência da linha nova já é a resposta
> certa. É o desenho da Fase 1 do pacote anterior pagando aqui.

**`reset_progress`** — as mesmas tabelas, por `cohort_id`, num `delete()` cada. Preserva
cadastro e `AiUsageEvent`.

## Fase 3 — Endpoints

Em `api/v1/cohorts.py`, ao lado das outras ações de turma:

```
POST /cohorts/{cohort_id}/sandbox/undo-last-closure   (ORG_ADMIN)
POST /cohorts/{cohort_id}/sandbox/reset               (ORG_ADMIN)
```

- `SandboxOnlyError` → 400 "Esta ação só existe em turma de teste";
- sem encerramento a desfazer → 404;
- resposta com as contagens do que saiu, para a UI dizer o que aconteceu.

## Fase 4 — Frontend

Sem CSS novo: `.tag` / `.tag--brand` já existem em `styles/tokens.css`.

| Onde | O quê |
|---|---|
| `pages/Cohorts.tsx` | badge `Teste` (`tag tag--brand`) na linha da turma |
| `pages/CohortEditor.tsx` | checkbox "Turma de teste" **apenas na criação**; na edição, badge somente leitura com a nota de que a marca não muda |
| `components/cohorts/CohortProgressPanel.tsx` | em turma de teste e para admin, dois botões ao final: **Desfazer último encerramento** e **Zerar andamento** |
| `lib/cohorts.ts` | `is_sandbox` e `SandboxRewind` nos tipos. As duas chamadas ficam inline no painel via `api.post`, como o `reingestNote` já faz — `cohorts.ts` é módulo puro de tipos e não importa `api` |

Interação pelos padrões que já existem: `useConfirm` com `tone: "danger"` (mensagem nomeando a
turma e o que será apagado) e `useApiAction` para feedback de sucesso/erro.

## Fase 5 — Verificação

**`bin/verify-sandbox`**, no mesmo padrão de `bin/verify-dinamismo`.

| # | Asserção |
|---|---|
| 1 | Turma real recusa as duas ações (e nada é apagado) |
| 2 | `undo` remove nota, cobertura, progresso, conversa e avaliações da aula |
| 3 | `undo` devolve a aula anterior a `ATIVA`/`DISPARADA` conforme `activated_at` |
| 4 | `undo` de uma sessão composta **faz a pendência da anterior voltar** |
| 5 | `undo` em sequência caminha para trás; sem encerramento, recusa |
| 6 | `reset` zera o andamento e **preserva** turma, matrículas, professores e divisão |
| 7 | `reset` preserva `AiUsageEvent` |
| 8 | Depois do `reset`, encerrar a aula 1 funciona como numa turma nova |

## Achado durante a validação

O `PATCH` nunca virou a marca no banco — a garantia estrutural funcionou. Mas a resposta voltava
`is_sandbox: false`: `_cohort_detail` e o serializer da lista montam o objeto campo a campo e não
repassavam o novo campo. Consequência prática: **o badge nunca apareceria e os botões nunca
apareceriam** — a feature ficaria invisível, com o dado correto no banco. Corrigido nos dois
serializers.

Vale registrar o padrão: neste arquivo, adicionar campo ao schema **não** basta; há dois pontos
de construção manual que precisam do campo explicitamente.

---

## Resultado

**`bin/verify-sandbox` — 24/24 verificações.** O script cria a própria turma de teste e a remove
no fim, então roda em sequência sem `db-reset` entre execuções.

```
1 · Turma real recusa as duas ações        3/3
2 · Sem encerramento, nada a desfazer      1/1
3 · Desfazer um encerramento simples       5/5   relato, cobertura, progresso, conversa
4 · Status da aula anterior restaurado     3/3   ATIVA ou DISPARADA conforme activated_at
5 · Pendência volta sozinha no composta    2/2
6 · Desfazer em sequência caminha atrás    1/1
7 · Zerar preserva cadastro e custos       4/4
8 · Depois de zerar, o ciclo roda de novo  2/2
9 · O raio de dano é de uma turma só       3/3   turma vizinha com relato, cobertura,
                                                 progresso e pendência sobrevive a tudo
```

Validado também pela API: turma real recusa as duas ações (400 com a mensagem certa), criação com
a marca, `PATCH` incapaz de virá-la nos dois sentidos, `undo` devolvendo a aula à fila, 404 quando
não há o que desfazer, `reset` preservando cadastro e a turma voltando a encerrar normalmente
depois — e `403` para professor nas duas ações e na criação.

`bin/verify-dinamismo` segue em 26/26 e `npm run build` limpo.

## Fora de escopo

Clonar turma, snapshot de banco, desfazer encerramento arbitrário no meio da sequência,
suprimir ou filtrar WhatsApp, e excluir turmas de teste dos agregados de custo.

## Ordem de execução

`1 → 2 → 3 → 4 → 5`.
