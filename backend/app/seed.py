"""Seeds development data.

Usage:
  python -m app.seed           # seed only if database is empty
  python -m app.seed --force   # wipe dev data and seed again
"""

import argparse
import asyncio
import subprocess

from sqlalchemy import select, text

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models import Base
from app.models.track import Lesson, Module, ModuleLevel, Track
from app.models.cohort import Cohort, CohortModuleProfessor, Enrollment
from app.models.user import Role, User

# Conteúdo publicado pelo designer na trilha — material que a turma estudou.
# Sem gabarito resolvido no texto: a Lira deve extrair entendimento na conversa.
# Relato, anexo do professor e material da trilha ficam fora do seed (fluxo manual).
LESSON_CRITICAL_READING = """\
Objetivo: separar o que está escrito do que você conclui ao ler um texto de trabalho.

Passos:
1. Fatos — o que está literalmente no texto (dá para apontar a frase).
2. Interpretações — o que você conclui a partir do que leu.
3. Pergunta-guia: "Isso está escrito ou estou supondo?"

Texto para aplicar (e-mail interno):
"Não vou aprovar isso agora."

Prática:
- Classifique o que é fato e o que é interpretação nesse e-mail.
- Traga um trecho curto de mensagem ou e-mail do seu trabalho e faça a mesma separação.

Na conversa com a Lira:
- Explique com suas palavras a diferença entre fato e interpretação.
- Aplique a pergunta-guia no e-mail acima antes de opinar sobre intenção ou clima da mensagem.
"""

LESSON_PARECER_STRUCTURE = """\
Objetivo: organizar um parecer curto em três blocos fixos.

Estrutura:
1. Contexto — qual é a situação e o pedido (2–3 frases).
2. Análise — fatos relevantes + interpretação fundamentada (sem opinião solta).
3. Recomendação — o que você sugere fazer, de forma objetiva.

Regra: cada bloco responde a uma pergunta diferente. Se misturar recomendação na análise, o leitor se perde.

Modelo (esqueleto):
---
Contexto: [Quem pediu o quê, sobre qual situação, em que prazo.]
Análise: [Fatos do caso.] [Interpretação fundamentada — sem recomendar ainda.]
Recomendação: [Ação objetiva que responde ao pedido inicial.]
---

Situação para praticar:
A área de operações pediu parecer sobre atraso na entrega de um fornecedor crítico.

Na conversa com a Lira:
- Identifique qual bloco está confuso em um rascunho seu ou no modelo acima.
- Separe o que seria fato e o que seria interpretação dentro da Análise.
"""

LESSON_FIRST_DRAFT = """\
Objetivo: produzir um rascunho legível sem polir demais.

Roteiro (15–20 minutos):
1. Contexto — escreva primeiro, em 3–4 frases.
2. Análise — fatos do caso, depois interpretação.
3. Recomendação — uma ação clara.

Durante o rascunho:
- Use frases curtas; marque [?] onde faltar dado.
- Não revise estilo ainda; revise só se o raciocínio fecha.

Critério de pronto: alguém de fora entende o problema e a proposta, mesmo com imperfeições.

Na conversa com a Lira:
- Leia em voz alta um trecho do seu rascunho (ou descreva o que escreveria).
- Aponte onde você ainda tem [?] e o que falta para fechar o raciocínio.
"""

LESSON_PEER_REVIEW = """\
Objetivo: revisar o parecer de um colega focando clareza, não "estilo bonito".

Trecho para revisar:
"O projeto está atrasado porque a equipe não se empenhou. Recomendo trocar o fornecedor."

Checklist:
1. O contexto deixa claro o pedido?
2. A análise separa fato de interpretação?
3. A recomendação responde ao pedido inicial?

Feedback útil: aponta trecho confuso + sugere pergunta ("o leitor vai entender de onde veio esse número?").

Na conversa com a Lira:
- Aplique o checklist no trecho acima.
- Diga o que você perguntaria ao autor antes de sugerir mudança de texto.
"""

LESSON_ARGUMENT = """\
Objetivo: argumentar com evidência, sem retórica vazia.

Boas práticas:
- Uma ideia por parágrafo.
- Cada afirmação relevante amarrada a um fato ou dado do caso.
- Evite absolutismos ("sempre", "nunca") sem prova.

Trecho para analisar:
"Acredito que o contrato deve ser rescindido. O fornecedor sempre atrasa e isso demonstra desinteresse.
Parece que a liderança não acompanha as entregas."

Teste rápido: sublinhe conectivos de opinião ("acredito", "parece", "sempre") e verifique se há fato antes deles.

Na conversa com a Lira:
- Separe, no trecho acima, o que é afirmação com evidência e o que é opinião sem amparo.
- Reformule uma frase mantendo só o que o texto ou o caso sustentam.
"""

LESSON_FINAL = """\
Objetivo: entregar versão final do parecer.

Checklist antes de enviar:
1. Leitura em voz alta (1 vez) — onde tropeçar, simplifique.
2. Contexto, análise e recomendação identificáveis em 10 segundos de olhada.
3. Título claro: assunto + posição/resposta.
4. Anexos citados no corpo estão de fato anexados.

Entrega: PDF ou e-mail com assunto objetivo; corpo sem anexos essenciais faltando.

Na conversa com a Lira:
- Simule o assunto do e-mail de entrega e diga em uma frase a posição do parecer.
- Indique o último ponto que você ainda revisaria antes de enviar.
"""

STAFF_USERS = [
    ("admin@certai.app", "Admin", Role.ADMIN, "admin12345"),
    ("designer@certai.app", "Designer", Role.DESIGNER, "design12345"),
]

PROFESSOR_USERS = [
    ("prof@certai.app", "Ana Paula Ribeiro", "prof12345"),
    ("marcos.ferreira@certai.app", "Marcos Ferreira", "prof12345"),
]

STUDENT_USERS = [
    ("aluno@certai.app", "Mariana Costa", "aluno12345", "5511999990001"),
    ("eriko@certai.app", "Ériko Sampaio", "aluno12345", "5585987385666"),
    ("juliana.mendes@certai.app", "Juliana Mendes", "aluno12345", "5511987650003"),
    ("pedro.almeida@certai.app", "Pedro Almeida", "aluno12345", "5511987650004"),
    ("camila.rocha@certai.app", "Camila Rocha", "aluno12345", "5511987650005"),
    ("lucas.nunes@certai.app", "Lucas Nunes", "aluno12345", "5511987650006"),
    ("fernanda.lima@certai.app", "Fernanda Lima", "aluno12345", "5511987650007"),
    ("bruno.carvalho@certai.app", "Bruno Carvalho", "aluno12345", "5511987650008"),
]

# Apenas dois matriculados na turma; os demais ficam disponíveis para matrícula em lote.
ENROLLED_STUDENT_EMAILS = {
    "aluno@certai.app",
    "eriko@certai.app",
}


def _run_alembic(*args: str) -> None:
    subprocess.run(["alembic", *args], check=True)


def _make_user(
    email: str, name: str, role: Role, password: str, whatsapp: str | None = None
) -> User:
    return User(
        email=email,
        name=name,
        role=role,
        hashed_password=hash_password(password),
        whatsapp=whatsapp,
    )


async def ensure_schema() -> None:
    """Garante tabelas base e aplica migrations pendentes (ex.: cohort_module_professors)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        has_alembic = await conn.scalar(text("SELECT to_regclass('public.alembic_version')"))
        has_legacy_professor = await conn.scalar(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'cohorts' AND column_name = 'professor_id' LIMIT 1"
            )
        )

    if not has_alembic:
        if has_legacy_professor:
            _run_alembic("stamp", "002_is_active")
        else:
            _run_alembic("stamp", "head")

    _run_alembic("upgrade", "head")


async def reset_database() -> None:
    """Remove all app tables (dev only). Equivalent to rails db:reset without recreating the DB."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


async def seed(*, force: bool = False) -> None:
    if force:
        print("Resetting database…")
        await reset_database()

    await ensure_schema()

    async with SessionLocal() as db:
        if not force and await db.scalar(select(User).limit(1)):
            print("Data already present; skipping seed.")
            print("Run: bin/db-reset   (or: python -m app.seed --force)")
            return

        users: list[User] = []
        for email, name, role, password in STAFF_USERS:
            users.append(_make_user(email, name, role, password))
        for email, name, password in PROFESSOR_USERS:
            users.append(_make_user(email, name, Role.PROFESSOR, password))
        for email, name, password, whatsapp in STUDENT_USERS:
            users.append(_make_user(email, name, Role.STUDENT, password, whatsapp=whatsapp))

        db.add_all(users)
        await db.flush()

        users_by_email = {user.email: user for user in users}
        prof_fundamentos = users_by_email["prof@certai.app"]
        prof_pratica = users_by_email["marcos.ferreira@certai.app"]

        track = Track(
            title="Comunicação escrita no trabalho",
            competency="Redigir pareceres claros e objetivos",
            description="Do rascunho à entrega, com revisão em pares e argumentação objetiva.",
            published=True,
        )
        db.add(track)
        await db.flush()

        m1 = Module(track_id=track.id, title="Fundamentos", level=ModuleLevel.BEGINNER, position=1)
        m2 = Module(track_id=track.id, title="Prática", level=ModuleLevel.INTERMEDIATE, position=2)
        db.add_all([m1, m2])
        await db.flush()

        db.add_all([
            Lesson(
                module_id=m1.id,
                title="Leitura crítica de textos",
                content=LESSON_CRITICAL_READING,
                position=1,
            ),
            Lesson(
                module_id=m1.id,
                title="Estrutura de um parecer",
                content=LESSON_PARECER_STRUCTURE,
                position=2,
            ),
            Lesson(
                module_id=m1.id,
                title="Primeiro rascunho",
                content=LESSON_FIRST_DRAFT,
                position=3,
            ),
            Lesson(
                module_id=m2.id,
                title="Revisão em pares",
                content=LESSON_PEER_REVIEW,
                position=1,
            ),
            Lesson(
                module_id=m2.id,
                title="Argumentação objetiva",
                content=LESSON_ARGUMENT,
                position=2,
            ),
            Lesson(
                module_id=m2.id,
                title="Entrega final",
                content=LESSON_FINAL,
                position=3,
            ),
        ])

        cohort = Cohort(name="VPF — Turma 1", track_id=track.id)
        db.add(cohort)
        await db.flush()
        db.add_all([
            CohortModuleProfessor(
                cohort_id=cohort.id,
                module_id=m1.id,
                professor_id=prof_fundamentos.id,
            ),
            CohortModuleProfessor(
                cohort_id=cohort.id,
                module_id=m2.id,
                professor_id=prof_pratica.id,
            ),
        ])

        for email in ENROLLED_STUDENT_EMAILS:
            db.add(Enrollment(cohort_id=cohort.id, student_id=users_by_email[email].id))

        await db.commit()

        print("Seed done.")
        print("")
        print("Logins principais:")
        print("  admin@certai.app / admin12345")
        print("  prof@certai.app / prof12345  (Ana Paula — Fundamentos)")
        print("  marcos.ferreira@certai.app / prof12345  (Marcos — Prática)")
        print("  aluno@certai.app / aluno12345  (Mariana Costa)")
        print("  eriko@certai.app / aluno12345  (Ériko Sampaio — WhatsApp real)")
        print("")
        print(f"Turma: {cohort.name}")
        print(f"  {len(ENROLLED_STUDENT_EMAILS)} alunos matriculados")
        print(f"  {len(STUDENT_USERS) - len(ENROLLED_STUDENT_EMAILS)} alunos disponíveis p/ matrícula em lote")
        print("  Demais alunos: senha aluno12345")
        print("")
        print("Personas sugeridas para testar conversas (respostas manuais no playground):")
        print("  Mariana (aluno@) — engajada, responde com texto")
        print("  Ériko (eriko@) — WhatsApp real")
        print("  Pedro (pedro.almeida@) — monossilábico (sim / não / bora)")
        print("  Camila (camila.rocha@) — auto-relato (consegui / tranquilo)")
        print("  Lucas (lucas.nunes@) — pede esclarecimento (como assim?)")
        print("")
        print("Fluxo manual após seed: professor encerra aula → ingestão → aluno conversa.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed development data")
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Wipe public schema and seed again (dev only)",
    )
    args = parser.parse_args()
    asyncio.run(seed(force=args.force))
