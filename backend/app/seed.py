"""Seeds development data. Usage: python -m app.seed"""

import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models import Base
from app.models.track import Lesson, Module, ModuleLevel, Track
from app.models.cohort import Cohort, CohortModuleProfessor, Enrollment
from app.models.user import Role, User


async def ensure_schema() -> None:
    """Garante tabelas base e aplica migrations pendentes (ex.: cohort_module_professors)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    cfg = Config("alembic.ini")
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
            command.stamp(cfg, "002_is_active")
        else:
            command.stamp(cfg, "head")

    command.upgrade(cfg, "head")


async def seed() -> None:
    await ensure_schema()

    async with SessionLocal() as db:
        if await db.scalar(select(User).limit(1)):
            print("Data already present; skipping seed.")
            return

        admin = User(email="admin@certai.app", name="Admin", role=Role.ADMIN,
                     hashed_password=hash_password("admin12345"))
        designer = User(email="designer@certai.app", name="Designer", role=Role.DESIGNER,
                        hashed_password=hash_password("design12345"))
        prof = User(email="prof@certai.app", name="Professor", role=Role.PROFESSOR,
                    hashed_password=hash_password("prof12345"))
        student = User(email="aluno@certai.app", name="Aluno", role=Role.STUDENT,
                       hashed_password=hash_password("aluno12345"))
        db.add_all([admin, designer, prof, student])
        await db.flush()

        # User-facing strings stay in Portuguese (product language).
        track = Track(title="Comunicação escrita no trabalho", competency="Redigir pareceres claros e objetivos",
                      description="Do rascunho à entrega, com revisão e argumentação.", published=True)
        db.add(track)
        await db.flush()

        m1 = Module(track_id=track.id, title="Fundamentos", level=ModuleLevel.BEGINNER, position=1)
        m2 = Module(track_id=track.id, title="Prática", level=ModuleLevel.INTERMEDIATE, position=2)
        db.add_all([m1, m2])
        await db.flush()

        db.add_all([
            Lesson(module_id=m1.id, title="Leitura crítica de textos", content="...", position=1),
            Lesson(module_id=m1.id, title="Estrutura de um parecer", content="...", position=2),
            Lesson(module_id=m1.id, title="Primeiro rascunho", content="...", position=3),
            Lesson(module_id=m2.id, title="Revisão em pares", content="...", position=1),
            Lesson(module_id=m2.id, title="Argumentação objetiva", content="...", position=2),
            Lesson(module_id=m2.id, title="Entrega final", content="...", position=3),
        ])

        cohort = Cohort(name="VPF — Turma 1", track_id=track.id)
        db.add(cohort)
        await db.flush()
        db.add_all([
            CohortModuleProfessor(cohort_id=cohort.id, module_id=m1.id, professor_id=prof.id),
            CohortModuleProfessor(cohort_id=cohort.id, module_id=m2.id, professor_id=prof.id),
        ])
        db.add(Enrollment(cohort_id=cohort.id, student_id=student.id))

        await db.commit()
        print("Seed done. Logins: admin@certai.app / admin12345 (and variants).")


if __name__ == "__main__":
    asyncio.run(seed())
