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

# Conteúdo enxuto e coeso para testes de conversa da Lira (mesma trilha de pareceres).
LESSON_CRITICAL_READING = """\
Objetivo: separar o que está escrito do que você conclui ao ler um texto de trabalho.

Passos:
1. Fatos — o que está literalmente no texto (dá para apontar a frase).
2. Interpretações — o que você conclui a partir do que leu.
3. Pergunta-guia: "Isso está escrito ou estou supondo?"

Exemplo (e-mail interno):
Texto: "Não vou aprovar isso agora."
- Fato: a pessoa diz que não aprova neste momento.
- Interpretação: ela pode estar aguardando o anexo do financeiro antes de decidir (se o anexo não aparece no e-mail, isso é suposição).

Prática: classifique fatos e interpretações antes de opinar sobre intenção ou clima da mensagem.
"""

LESSON_PARECER_STRUCTURE = """\
Objetivo: organizar um parecer curto em três blocos fixos.

Estrutura:
1. Contexto — qual é a situação e o pedido (2–3 frases).
2. Análise — fatos relevantes + interpretação fundamentada (sem opinião solta).
3. Recomendação — o que você sugere fazer, de forma objetiva.

Regra: cada bloco responde a uma pergunta diferente. Se misturar recomendação na análise, o leitor se perde.
"""

LESSON_FIRST_DRAFT = """\
Objetivo: produzir um rascunho legível sem polir demais.

Roteiro:
- Escreva em 15–20 minutos, em ordem: contexto → análise → recomendação.
- Use frases curtas; marque [?] onde faltar dado.
- Não revise estilo ainda; revise só se o raciocínio fecha.

Critério de pronto: alguém de fora entende o problema e a proposta, mesmo com imperfeições.
"""

LESSON_PEER_REVIEW = """\
Objetivo: revisar o parecer de um colega focando clareza, não "estilo bonito".

Checklist:
1. O contexto deixa claro o pedido?
2. A análise separa fato de interpretação?
3. A recomendação responde ao pedido inicial?

Feedback útil: aponta trecho confuso + sugere pergunta ("o leitor vai entender de onde veio esse número?").
"""

LESSON_ARGUMENT = """\
Objetivo: argumentar com evidência, sem retórica vazia.

Boas práticas:
- Uma ideia por parágrafo.
- Cada afirmação relevante amarrada a um fato ou dado do caso.
- Evite absolutismos ("sempre", "nunca") sem prova.

Teste rápido: sublinhe conectivos de opinião ("acredito", "parece") e veja se há fato antes deles.
"""

LESSON_FINAL = """\
Objetivo: entregar versão final do parecer.

Antes de enviar:
1. Leitura em voz alta (1 vez) — onde tropeçar, simplifique.
2. Confira se contexto, análise e recomendação estão identificáveis em 10 segundos de olhada.
3. Título claro: assunto + posição/resposta.

Entrega: PDF ou e-mail com assunto objetivo; corpo sem anexos essenciais faltando.
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
    ("aluno@certai.app", "Mariana Costa", "aluno12345"),
    ("rafael.souza@certai.app", "Rafael Souza", "aluno12345"),
    ("juliana.mendes@certai.app", "Juliana Mendes", "aluno12345"),
    ("pedro.almeida@certai.app", "Pedro Almeida", "aluno12345"),
    ("camila.rocha@certai.app", "Camila Rocha", "aluno12345"),
    ("lucas.nunes@certai.app", "Lucas Nunes", "aluno12345"),
    ("fernanda.lima@certai.app", "Fernanda Lima", "aluno12345"),
    ("bruno.carvalho@certai.app", "Bruno Carvalho", "aluno12345"),
]

# Apenas dois matriculados na turma; os demais ficam disponíveis para matrícula em lote.
ENROLLED_STUDENT_EMAILS = {
    "aluno@certai.app",
    "rafael.souza@certai.app",
}


def _run_alembic(*args: str) -> None:
    subprocess.run(["alembic", *args], check=True)


def _make_user(email: str, name: str, role: Role, password: str) -> User:
    return User(
        email=email,
        name=name,
        role=role,
        hashed_password=hash_password(password),
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
        for email, name, password in STUDENT_USERS:
            users.append(_make_user(email, name, Role.STUDENT, password))

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
        print("")
        print(f"Turma: {cohort.name}")
        print(f"  {len(ENROLLED_STUDENT_EMAILS)} alunos matriculados")
        print(f"  {len(STUDENT_USERS) - len(ENROLLED_STUDENT_EMAILS)} alunos disponíveis p/ matrícula em lote")
        print("  Demais alunos: senha aluno12345")


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
