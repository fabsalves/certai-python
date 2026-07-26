# Avaliação por camadas — plano de execução (CertAI)

Salvar em `docs/avaliacao-camadas.plan.md` no `certai-python`.
Estado atual detalhado: `docs/scores.estado-atual.md`.

**Projeto não está em produção.** Sem preocupação com dados existentes,
compatibilidade ou migração de histórico. Reestruturar livremente.

---

## 1. Objetivo

Hoje existe só a camada de base: micro-scores que a Lira registra durante a
conversa, aula por aula.

Falta construir a **avaliação consolidada por aluno** em três escopos:

1. **Aula** — o quanto o aluno compreendeu daquela aula
2. **Módulo** — o quanto compreendeu do módulo
3. **Trilha** — o quanto compreendeu da jornada inteira

O núcleo é **compreensão**. Lacuna é consequência (e habilita ações como
oferecer aula extra), não o objetivo.

Definido na reunião de 15/06 (Pedro, Fabiano, Horácio, Ériko): avaliações
individuais por aula e por módulo, culminando num assessment geral.

---

## 2. Decisões cravadas

| Tema | Decisão |
|---|---|
| Unidade | **Por aluno**, em cada escopo (aula, módulo, trilha) |
| Avaliação de aula | Por aluno da turma — não é avaliação da turma |
| Quem avalia | IA em **papel de avaliador**, não a Lira (evita viés de quem conduziu a conversa). Mesma infra do sistema, prompt e papel próprios. Reusar `settings.EVALUATOR_MODEL` |
| Base de julgamento | Nasce sempre dos **micro-scores**, em todas as camadas |
| Saída | **Nível qualitativo** (`very_low\|low\|medium\|high`, o mesmo enum já existente) + **parecer** em texto + **lacunas** em texto. Sem nota, sem percentual, sem média |
| Consistência | Mesmo formato de saída nas três camadas |
| Heurística | **Proibida.** A IA julga livremente com os dados dispostos |
| Persistência | Toda avaliação é registrada por aluno + escopo |
| Reprocessamento | Append-only; leitura pega o registro mais recente |
| Visão de turma | **Derivada** da leitura das avaliações dos alunos. Não existe avaliação de IA da turma |
| `evaluate_cohort_gaps` | **Remover** (junto com `sweep_evaluations` e a entrada no beat). Manter só o `EVALUATOR_MODEL` |

---

## 3. Desenho por camada

### Aula (por aluno)

Insumos:
- Material da aula (`Lesson.content`)
- Relato e anexo do professor (`CohortLessonNote`: `summary`, `unclear_points`,
  `attachment_knowledge_base`, `professor_transcript`) → **este é o escopo**:
  o que aquela aula, naquela turma, exigia
- Micro-scores do aluno naquela aula, **com a evidência**
- A **conversa** do aluno naquela aula

### Módulo (por aluno)

Insumos:
- As **avaliações de aula** daquele módulo, para aquele aluno
- Micro-scores do aluno no módulo

Sem conversas.

### Trilha (por aluno)

Insumos:
- As **avaliações de módulo** daquele aluno
- Micro-scores do aluno na trilha

Sem conversas.

**Por que hierárquico:** cada camada lê a de baixo, não o material bruto inteiro.
Mantém simples, barato e escalável, e faz o acompanhamento da jornada ficar
coerente — a trilha vê a história consolidada, não um oceano de transcrição.

---

## 4. Gatilhos (reusam a máquina de estados existente)

- Aula concluída para o aluno (`concluded_at`) → avalia a **aula**
- Todas as aulas do módulo concluídas para o aluno → avalia o **módulo**
  (encadeado após a task de avaliação de aula terminar — evita corrida
  em que o módulo rodaria sem a avaliação da última aula)
- Todos os módulos da trilha **com avaliação de módulo** para o aluno →
  avalia a **trilha** (encadeado após a task de avaliação de módulo)

Nenhum mecanismo novo de disparo.

---

## 5. Fases

- **Fase 1** — Modelo + migration (persistência)
- **Fase 2** — Avaliador da camada de aula + gatilho + remoção do job antigo
- **Fase 3** — Camadas de módulo e trilha
- **Fase 4** — Exposição na plataforma (frente própria, não hoje)

Uma fase por vez, com teste antes de avançar.

---

## Prompt — Fase 1 (modelo + migration)

```
FASE 1 de 3: modelo e persistência da avaliação por camadas. Projeto certai-python
(entre em certai-python primeiro; não confundir com cert-ai). NÃO está em produção.
Contexto completo: docs/avaliacao-camadas.plan.md. Não implementar avaliador nem
gatilho nesta fase.

CRIAR o modelo StudentAssessment (tabela student_assessments) em
backend/app/models/assessment.py (junto do MicroScore, mesmo domínio):

- cohort_id: FK cohorts.id, CASCADE, indexado, NOT NULL
- student_id: FK users.id, CASCADE, indexado, NOT NULL
- scope: enum novo AssessmentScope com valores "lesson" | "module" | "track", NOT NULL
- lesson_id: FK lessons.id, SET NULL, nullable
- module_id: FK modules.id, SET NULL, nullable
- track_id:  FK tracks.id,  SET NULL, nullable
  (exatamente um dos três é preenchido, conforme o scope — não criar constraint
   complexa para isso; a regra vive no serviço)
- level: enum Level EXISTENTE (very_low|low|medium|high), NULLABLE
  (nulo = sem evidência suficiente para atribuir nível — é informação válida,
   não forçar um nível quando não há base)
- assessment: Text, default "" — o parecer sobre o quanto o aluno compreendeu
- gaps: Text, default "" — lacunas identificadas (pode ficar vazio)
- created_at/updated_at vêm do Base

Sem UniqueConstraint: é append-only, a leitura pega o mais recente por
(student, scope, scope_id).

MIGRATION: criar uma migration NOVA na sequência (confirmar o head atual com
alembic heads; provavelmente 012). down_revision apontando para o head correto.
NÃO editar migrations existentes.

Validar: bin/db-reset roda limpo, a cadeia de migrations sobe até a nova sem
conflito de heads, e a tabela nasce com as colunas.

Ao final: git status --short + diff do modelo + conteúdo da migration nova +
confirmação de que o db-reset subiu limpo. Não avançar para a Fase 2.
```

---

## Prompt — Fase 2 (avaliador da camada de aula)

```
FASE 2 de 3: avaliador da camada de AULA. Projeto certai-python. NÃO está em
produção. Contexto: docs/avaliacao-camadas.plan.md. Fase 1 (modelo
StudentAssessment) já está pronta.

1. SERVIÇO NOVO (ex.: backend/app/services/assessment/lesson_assessment_service.py)
   que, dado (cohort_id, student_id, lesson_id):

   a) Monta os insumos:
      - Material da aula: Lesson.content
      - Escopo daquela turma: CohortLessonNote mais recente de (cohort, lesson) —
        summary, unclear_points, attachment_knowledge_base, professor_transcript
      - Micro-scores do aluno naquela aula, INCLUINDO o campo evidence
      - A conversa do aluno naquela aula (conversa lesson-scoped, mensagens)

   b) Chama a IA no papel de AVALIADOR:
      - Modelo: settings.EVALUATOR_MODEL
      - Prompt próprio, NÃO usar LIRA_TONE nem a persona da Lira. É um avaliador
        interno, não conversa com aluno. Escrever em pt-BR.
      - O avaliador recebe o que a aula EXIGIA (material + relato do professor) e
        o que o aluno DEMONSTROU (micro-scores com evidência + conversa), e julga
        livremente o quanto o aluno compreendeu.
      - PROIBIDO: nota, percentual, média, checklist, heurística. Julgamento
        qualitativo livre.
      - Saída pedida em JSON com exatamente: level (very_low|low|medium|high ou
        null se não houver evidência suficiente), assessment (parecer), gaps
        (lacunas; string vazia se não houver).

   c) Persiste um StudentAssessment com scope="lesson", lesson_id preenchido.
      IMPORTANTE: usar o helper coerce_llm_text_field (já existe em
      app/services/ingestion/__init__.py) nos campos de texto antes de gravar —
      o LLM já quebrou a ingestão antes devolvendo dict onde se esperava string.

2. GATILHO: quando a aula é concluída para o aluno (StudentProgressService.conclude,
   que grava concluded_at), enfileirar uma task Celery que roda a avaliação.
   Seguir o padrão já usado no projeto (enqueue after_commit, como
   ingest_lesson_completion). A avaliação NÃO deve bloquear a conclusão nem a
   conversa: se falhar, a aula continua concluída.

3. REMOVER o avaliador antigo, que é superado por este desenho:
   - task evaluate_cohort_gaps e _evaluate_gaps (workers/tasks.py)
   - task sweep_evaluations e _sweep_evaluations
   - a entrada "nightly-gap-evaluation" no beat_schedule (workers/celery_app.py)
   - MANTER settings.EVALUATOR_MODEL (agora usado pelo novo avaliador)
   Confirmar que não sobrou referência órfã.

Ao final: git status --short + diff dos arquivos + um script de verificação
(scripts/verify_lesson_assessment.py) que exercita o fluxo: conclui uma aula para
um aluno → avaliação é gerada e persistida com level/assessment/gaps. Não avançar
para a Fase 3.
```

---

## Prompt — Fase 3 (camadas de módulo e trilha)

```
FASE 3 de 3: camadas de MÓDULO e TRILHA. Projeto certai-python. Contexto:
docs/avaliacao-camadas.plan.md. Fases 1 e 2 prontas (modelo + avaliador de aula).

Mesmo motor da Fase 2, insumos HIERÁRQUICOS (não reler conversas):

1. MÓDULO (por aluno): insumos = as avaliações de AULA daquele módulo para aquele
   aluno (as mais recentes de cada aula) + micro-scores do aluno no módulo.
   Persiste StudentAssessment com scope="module", module_id preenchido.

2. TRILHA (por aluno): insumos = as avaliações de MÓDULO daquele aluno (as mais
   recentes) + micro-scores do aluno na trilha.
   Persiste StudentAssessment com scope="track", track_id preenchido.

Mesmo papel de avaliador, mesmo formato de saída (level nullable + assessment +
gaps), mesmas proibições (sem nota, percentual, média, heurística). Reusar o
máximo do serviço da Fase 2 — não duplicar lógica; o que muda são os insumos.

GATILHOS:
- Todas as aulas do módulo concluídas para o aluno → avalia o módulo
- Todos os módulos da trilha com avaliação de módulo para o aluno → avalia a trilha
Usar a máquina de estados existente (StudentLessonProgress) para detectar isso.
Não inventar mecanismo novo de disparo.

Ao final: git status --short + diff + script de verificação que exercita a cadeia
completa: concluir todas as aulas de um módulo → avaliação de módulo nasce;
concluir todos os módulos → avaliação de trilha nasce. Confirmar que módulo e
trilha NÃO releem conversas.
```

---

## 6. Decisões que ficaram para a Fase 4 (exposição)

- Onde professor, aluno e instituição veem as avaliações
- Visão de turma: derivada da leitura das avaliações por aluno (distribuição de
  níveis, lacunas recorrentes) — sem nova chamada de IA
- Se vale registrar quais micro-scores sustentaram cada avaliação
  (rastreabilidade para credencial verificável)

---

## 7. Princípios do projeto (não negociáveis)

- A inteligência decide; o código registra o efeito.
- Mínimo de estrutura, máxima liberdade da IA.
- Sem heurística, sem keyword-matching, sem determinismo de fluxo.
- O simples que seja suficiente. Não criar complexidade.
- Uma etapa por vez, com teste antes de avançar.
