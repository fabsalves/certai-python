# CertAI

Produto novo, AI-first, para **certificar jornadas de aprendizado com garantia de absorção**.
A IA decide; o código persiste.

> Não é uma reescrita do CertAI antigo. É um produto novo, construído do zero, com core
> AI-first. É o embrião do *companion* que poderá ser embutido na Ânima.

---

## Princípios

- **A IA é quem mais toma decisões.** Zero heurística, zero inferência por palavra, zero
  regex, zero determinismo de fluxo. Inteligência real e contexto bem montado.
- **Tools são arsenal, não restrição.** Quanto mais capacidade de agir, melhor. O que se
  minimiza são *regras textuais* dadas ao motor.
- **Restrição vira estrutura.** A regra "não ensine o futuro" não é dita à IA: o conteúdo
  futuro simplesmente não entra no contexto (ver `ContextBuilder`).
- **Projeto enxuto.** Um motor único; o que diverge é o contexto, não o código.

## Separação de papéis (o que amarra o ciclo)

| Papel | Quem | Faz |
|---|---|---|
| Define **o quê** | Designer / Admin | Cadastra trilha → módulos → aulas, em sequência fixa. |
| Define **quando avançou** | Professor | Sinaliza, por turma, que a aula foi estudada. É o gatilho. |
| **Executa e garante** | IA (Lira) | Opera no que está liberado, decide via tools, garante o aprendizado. |

O encerramento de aula pelo professor **avança a turma e libera o contexto** no mesmo evento.

---

## Stack

- **Backend:** Python · FastAPI (async) · SQLAlchemy 2 · PostgreSQL · Redis
- **Async:** Celery (worker) + Celery Beat (agendados) + Flower (listagem/monitoramento)
- **Frontend:** React 19 · Vite 6 · TypeScript (em `frontend/`)
- **IA:** OpenAI (motor, humanizador, avaliador — mesmo provedor do Realtime com alunos) · Groq/Whisper (transcrição)
- **Segurança:** JWT access/refresh, bcrypt, RBAC por papel, e-mail único (sempre em minúsculas), rotas públicas/privadas,
  CORS restrito, security headers, rate limiting, segregação por `turma_id`.

---

## Arquitetura de IA

```
mensagem do aluno
      │
      ▼
ContextBuilder ──► monta o bundle por escopo (aula/módulo/trilha),
                   recortado pela progressão da turma:
                     • mapa da trilha  -> sempre
                     • conteúdo        -> só o que a turma já estudou
      │
      ▼
   MOTOR (único, scope-agnostic) ──► loop de raciocínio + tools
      │   tools: escalar_escopo, pontuar_entendimento, …
      │   (escalar = chamar tool e o resultado VOLTA para a IA)
      ▼
 HUMANIZADOR (passe final) ──► remove tom robótico, mantém o conteúdo
      │
      ▼
  resposta ao aluno
```

Avaliação: micro-scores qualitativos (muito baixo → alto), nunca nota numérica. Uma IA
externa (job em batch) lê os scores e aponta lacunas, sem média única.

Conversas com alunos usam a **OpenAI** (Chat Completions hoje; Realtime em breve), para
manter o mesmo ecossistema de modelos e voz ao longo do fluxo.

---

## Dev local

### Pré-requisitos

- Python 3.11+
- Node.js 20+
- PostgreSQL e Redis rodando localmente
- [Foreman](https://github.com/ddollar/foreman) (`gem install foreman`)

### 1. Variáveis de ambiente

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
ln -sf ../.env backend/.env
```

Ajuste no `.env`: `SECRET_KEY`, credenciais do Postgres e chaves de IA (`OPENAI_API_KEY`, `GROQ_API_KEY`).

### 2. Infra local

Postgres e Redis precisam estar acessíveis nas portas do `.env` (padrão: `5432` e `6379`).

```bash
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis
createdb certai   # se o banco ainda não existir
```

### 3. Backend

O venv fica **dentro de `backend/`** (não na raiz do projeto):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> Se `pip` der `command not found`, o venv provavelmente foi criado no lugar errado
> ou o terminal ficou com um `activate` antigo. Rode `deactivate`, abra um terminal novo
> e repita os comandos acima a partir de `cd backend`.

Migrations e seed (com o venv ativo, ainda em `backend/`):

```bash
alembic revision --autogenerate -m "inicial"   # só na primeira vez
alembic upgrade head
python -m app.seed
```

Na raiz do projeto também dá para usar:

```bash
bin/db-seed          # seed se o banco estiver vazio
bin/db-seed --force  # apaga dados de dev e re-semeia
bin/db-reset         # atalho para --force
```

O seed traz trilha com **6 aulas** de conteúdo real, **2 professores**, **8 alunos** (2 já matriculados na turma) e o restante disponível para testar matrícula em lote.

### 4. Frontend

```bash
cd frontend
npm install
```

### 5. Subir tudo

Na raiz do projeto:

```bash
bin/dev
```

O Foreman sobe API, worker, beat, flower e frontend de uma vez (`Procfile.dev`).

| Serviço | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API (docs) | http://localhost:8000/api/v1/openapi.json |
| Playground (admin) | http://localhost:5173/admin/playground |
| Flower (jobs) | http://localhost:5555 |

### WhatsApp — testar sem inbound pelo celular

Depois de encerrar uma aula (cria a conversa WhatsApp), simule mensagens do aluno:

```bash
./bin/send-message 'Achei difícil a parte sobre tom formal'
./bin/send-audio fixtures/audio/audio-teste.ogg   # requer GROQ_API_KEY
```

Guia completo: [`docs/whatsapp-dev-local.md`](docs/whatsapp-dev-local.md)

Logins de teste (após o seed):

| Papel | E-mail | Senha |
|---|---|---|
| Admin | admin@certai.app | admin12345 |
| Designer | designer@certai.app | design12345 |
| Professor (Fundamentos) | prof@certai.app | prof12345 |
| Professor (Prática) | marcos.ferreira@certai.app | prof12345 |
| Aluno (matriculado) | aluno@certai.app | aluno12345 |
| Aluno (matriculado) | rafael.souza@certai.app | aluno12345 |

Demais alunos do seed: senha `aluno12345` (úteis para matrícula em lote).

## Docker (opcional)

```bash
cp .env.example .env
docker compose up --build
```

O backend roda o seed automaticamente no compose de dev.

---

## Estrutura

```
certai/
├── backend/
│   ├── app/
│   │   ├── core/        config, db, redis, security, deps (RBAC)
│   │   ├── models/      User, Track/Module/Lesson, Cohort/Progress, Conversation, Assessment
│   │   ├── schemas/     contratos Pydantic
│   │   ├── api/v1/      auth, users, tracks, cohorts, conversations
│   │   ├── services/    lesson_completion (cycle trigger)
│   │   ├── ai/          engine, context_builder, tools, humanizer, client
│   │   └── workers/     celery_app, tasks (Groq, dispatch, evaluation)
│   ├── alembic/         migrations
│   └── Dockerfile
├── frontend/            React + Vite (design institucional)
│   └── src/
│       ├── lib/         api, auth, confirm, feedback, validation, useApiAction
│       ├── components/  AppShell, ProtectedRoute, UI (Select, ConfirmDialog)
│       └── pages/       Login, Dashboard, Tracks, Cohorts, Learn, Playground
├── bin/dev              foreman — sobe API, workers e frontend
├── bin/db-seed          seed do banco (aceita --force)
├── bin/db-reset         re-semeia o banco de dev
├── bin/send-message     simula inbound WhatsApp (texto) — ver docs/whatsapp-dev-local.md
├── bin/send-audio       simula inbound WhatsApp (áudio)
├── docs/                guias (WhatsApp local, template Cinndi, …)
├── Procfile.dev
├── docker-compose.yml
└── .env.example
```

## Roadmap

- **v1:** tudo acima.
- **v1.2:** limitador de contexto por nível do aluno (já modelado em `progresso_turma`;
  a inteligência fina de corte amadurece aqui) + integração WhatsApp/QR.
