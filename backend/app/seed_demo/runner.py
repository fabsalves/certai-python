"""Demo cohort seed: deterministic, no AI, idempotent.

Usage (after bin/db-reset):
  python -m app.seed_demo
  # or: bin/seed-demo
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from random import Random

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.assessment import (
    AssessmentScope,
    CohortLessonNote,
    Level,
    MicroScore,
    StudentAssessment,
)
from app.models.cohort import (
    Cohort,
    CohortModuleProfessor,
    CohortModuleStudent,
    CohortProgress,
    Enrollment,
)
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.models.track import Lesson, Module, Track
from app.models.user import Role, User
from app.seed_demo.notes import LESSON_NOTES
from app.seed_demo.profiles import SKIP, StudentPlan, build_plans
from app.seed_demo.students import build_demo_students
from app.seed_demo.texts import lesson_text, module_text, pick_micros, track_text

DEMO_COHORT_NAME = "VPF, Turma Demo"
DEMO_EMAIL_DOMAIN = "@demo.certai.app"
TRACK_TITLE = "Comunicação escrita no trabalho"
RNG_SEED = 42
DEMO_PASSWORD = "aluno12345"

PROF_FUNDAMENTOS_EMAIL = "prof@certai.app"
PROF_PRATICA_EMAILS = (
    "marcos.ferreira@certai.app",
    "prof@certai.app",
    "camila.oliveira@certai.app",
)

LEVEL_ENUM = {
    "high": Level.HIGH,
    "medium": Level.MEDIUM,
    "low": Level.LOW,
    "very_low": Level.VERY_LOW,
}

LESSON_TITLE_TO_KEY = {
    "Leitura crítica de textos": "leitura_critica",
    "Estrutura de um parecer": "estrutura_parecer",
    "Primeiro rascunho": "primeiro_rascunho",
    "Revisão em pares": "revisao_pares",
    "Argumentação objetiva": "argumentacao",
    "Entrega final": "entrega_final",
}

MODULE_TITLE_TO_KEY = {
    "Fundamentos": "fundamentos",
    "Prática": "pratica",
}


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _lesson_anchor(now: datetime, lesson_index: int) -> datetime:
    """Spread lessons across ~3 weeks (oldest first)."""
    days_ago = 20 - lesson_index * 3
    return _utc(now - timedelta(days=days_ago, hours=10))


async def _require_base(
    db,
) -> tuple[Track, list[Module], list[Lesson], User, list[User]]:
    track = await db.scalar(
        select(Track)
        .where(Track.title == TRACK_TITLE)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    if track is None:
        print(
            "Trilha base não encontrada. Rode antes: bin/db-reset",
            file=sys.stderr,
        )
        raise SystemExit(1)

    modules = sorted(track.modules, key=lambda m: m.position)
    lessons: list[Lesson] = []
    for mod in modules:
        lessons.extend(sorted(mod.lessons, key=lambda lesson: lesson.position))

    if len(modules) != 2 or len(lessons) != 6:
        print(
            f"Trilha inesperada: {len(modules)} módulos, {len(lessons)} aulas "
            "(esperado 2 e 6).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    for lesson in lessons:
        if lesson.title not in LESSON_TITLE_TO_KEY:
            print(f"Aula sem mapeamento no seed-demo: {lesson.title!r}", file=sys.stderr)
            raise SystemExit(1)

    prof_fundamentos = await db.scalar(
        select(User).where(User.email == PROF_FUNDAMENTOS_EMAIL)
    )
    pratica_profs: list[User] = []
    for email in PROF_PRATICA_EMAILS:
        prof = await db.scalar(select(User).where(User.email == email))
        if prof is None:
            print(
                f"Professor {email} não encontrado. Rode antes: bin/db-reset",
                file=sys.stderr,
            )
            raise SystemExit(1)
        pratica_profs.append(prof)

    if prof_fundamentos is None:
        print(
            "Professores do seed base não encontrados. Rode antes: bin/db-reset",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return track, modules, lessons, prof_fundamentos, pratica_profs


async def _wipe_demo(db) -> None:
    existing = await db.scalar(select(Cohort).where(Cohort.name == DEMO_COHORT_NAME))
    if existing is not None:
        # Notes and progress reference the classes, which the cohort delete also
        # removes -- clear them first so the ordering never trips the FK.
        await db.execute(
            delete(CohortLessonNote).where(CohortLessonNote.cohort_id == existing.id)
        )
        await db.execute(
            delete(CohortProgress).where(CohortProgress.cohort_id == existing.id)
        )
        await db.flush()
        await db.delete(existing)
        await db.flush()

    demo_users = (
        await db.scalars(select(User).where(User.email.like(f"%{DEMO_EMAIL_DOMAIN}")))
    ).all()
    for user in demo_users:
        await db.delete(user)
    if demo_users:
        await db.flush()


def _print_summary(
    *,
    track_title: str,
    students: list,
    plans: dict[str, StudentPlan],
    lessons: list[Lesson],
    lesson_level_counts: list[Counter],
) -> None:
    profile_counts = Counter(s.profile for s in students)
    print("Demo seed done.")
    print("")
    print(f"Turma: {DEMO_COHORT_NAME}")
    print(f"Trilha: {track_title}")
    print(f"Alunos: {len(students)}")
    print("Perfis:")
    for key in (
        "destaque",
        "consistente",
        "irregular",
        "dificuldade",
        "pouco_engajado",
        "atrasado",
        "pendente_avaliacao",
    ):
        print(f"  {key}: {profile_counts[key]}")
    print("")
    print("Distribuição de níveis por aula (entre matriculados):")
    for idx, lesson in enumerate(lessons):
        c = lesson_level_counts[idx]
        print(
            f"  {idx + 1}. {lesson.title}: "
            f"high={c['high']} medium={c['medium']} low={c['low']} "
            f"very_low={c['very_low']} sem_evidencia={c['sem_evidencia']} "
            f"pendente={c['pendente']} nao_concluiu={c['nao_concluiu']}"
        )
    print("")
    print("Logins (seed base):")
    print("  admin@certai.app / admin12345")
    print("  prof@certai.app / prof12345  (Ana — Fundamentos + 1/3 da Prática)")
    print("  marcos.ferreira@certai.app / prof12345  (Marcos — 1/3 da Prática)")
    print("  camila.oliveira@certai.app / prof12345  (Camila — 1/3 da Prática)")
    print(f"Alunos demo: senha {DEMO_PASSWORD} (e-mails *@demo.certai.app)")


async def seed_demo() -> None:
    rng = Random(RNG_SEED)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    students_meta = build_demo_students()
    plans = build_plans(students_meta, rng)
    password_hash = hash_password(DEMO_PASSWORD)

    async with SessionLocal() as db:
        track, modules, lessons, prof_fundamentos, pratica_profs = await _require_base(db)
        await _wipe_demo(db)

        cohort = Cohort(name=DEMO_COHORT_NAME, track_id=track.id)
        db.add(cohort)
        await db.flush()

        # Fundamentos: 1 professor (Ana). Prática: 3 professors with even roster
        # so the demo exercises both single- and multi-professor module shapes.
        fundamentos_class = CohortModuleProfessor(
            cohort_id=cohort.id,
            module_id=modules[0].id,
            professor_id=prof_fundamentos.id,
        )
        pratica_classes = [
            CohortModuleProfessor(
                cohort_id=cohort.id,
                module_id=modules[1].id,
                professor_id=prof.id,
            )
            for prof in pratica_profs
        ]
        db.add_all([fundamentos_class, *pratica_classes])
        await db.flush()

        classes_by_module = {
            modules[0].id: [fundamentos_class],
            modules[1].id: pratica_classes,
        }

        notes_by_key = {n.lesson_key: n for n in LESSON_NOTES}
        for idx, lesson in enumerate(lessons):
            key = LESSON_TITLE_TO_KEY[lesson.title]
            note = notes_by_key[key]
            anchor = _lesson_anchor(now, idx)
            for module_class in classes_by_module[lesson.module_id]:
                db.add(
                    CohortLessonNote(
                        cohort_id=cohort.id,
                        lesson_id=lesson.id,
                        module_professor_id=module_class.id,
                        summary=note.summary,
                        unclear_points=note.unclear_points,
                        professor_transcript=note.professor_transcript,
                        ingestion_status="done",
                        created_at=anchor,
                        updated_at=anchor,
                    )
                )
                db.add(
                    CohortProgress(
                        cohort_id=cohort.id,
                        lesson_id=lesson.id,
                        module_professor_id=module_class.id,
                        global_position=idx + 1,
                        created_at=anchor + timedelta(minutes=5),
                        updated_at=anchor + timedelta(minutes=5),
                    )
                )

        users: list[User] = []
        for meta in students_meta:
            user = User(
                email=meta.email,
                name=meta.name,
                role=Role.STUDENT,
                hashed_password=password_hash,
            )
            users.append(user)
            db.add(user)
        await db.flush()

        users_by_email = {u.email: u for u in users}
        for meta in students_meta:
            db.add(
                Enrollment(
                    cohort_id=cohort.id,
                    student_id=users_by_email[meta.email].id,
                )
            )

        for position, meta in enumerate(students_meta):
            db.add(
                CohortModuleStudent(
                    module_professor_id=pratica_classes[
                        position % len(pratica_classes)
                    ].id,
                    student_id=users_by_email[meta.email].id,
                )
            )

        lesson_level_counts = [Counter() for _ in lessons]

        for student_ord, meta in enumerate(students_meta):
            plan = plans[meta.email]
            student = users_by_email[meta.email]
            student_hour_offset = timedelta(minutes=15 * (student_ord % 16))

            for idx, lesson in enumerate(lessons):
                key = LESSON_TITLE_TO_KEY[lesson.title]
                anchor = _lesson_anchor(now, idx)
                concluded = plan.concluded[idx]

                if concluded:
                    disparada_at = anchor + timedelta(hours=1) + student_hour_offset
                    activated_at = disparada_at + timedelta(hours=2)
                    concluded_at = activated_at + timedelta(hours=6 + (student_ord % 5))
                    db.add(
                        StudentLessonProgress(
                            cohort_id=cohort.id,
                            student_id=student.id,
                            lesson_id=lesson.id,
                            status=StudentLessonProgressStatus.CONCLUIDA,
                            disparada_at=disparada_at,
                            activated_at=activated_at,
                            concluded_at=concluded_at,
                            created_at=disparada_at,
                            updated_at=concluded_at,
                        )
                    )
                else:
                    # Mid-journey: first open lesson active, later ones only disparada.
                    first_open = next(i for i, c in enumerate(plan.concluded) if not c)
                    disparada_at = anchor + timedelta(hours=1) + student_hour_offset
                    if idx == first_open:
                        status = StudentLessonProgressStatus.ATIVA
                        activated_at = disparada_at + timedelta(hours=1)
                    else:
                        status = StudentLessonProgressStatus.DISPARADA
                        activated_at = None
                    db.add(
                        StudentLessonProgress(
                            cohort_id=cohort.id,
                            student_id=student.id,
                            lesson_id=lesson.id,
                            status=status,
                            disparada_at=disparada_at,
                            activated_at=activated_at,
                            created_at=disparada_at,
                            updated_at=disparada_at,
                        )
                    )
                    lesson_level_counts[idx]["nao_concluiu"] += 1
                    continue

                if plan.skip_assessment[idx]:
                    lesson_level_counts[idx]["pendente"] += 1
                    # Still may have micro-scores from conversation before assessment.
                    level_for_micro = plan.lesson_levels[idx]
                    if level_for_micro is not SKIP and isinstance(level_for_micro, str):
                        micros = pick_micros(
                            key,
                            level_for_micro,
                            rng,
                            mode=plan.micro_mode,
                            salt=student_ord * 10 + idx,
                        )
                        for m_i, micro in enumerate(micros):
                            ts = concluded_at + timedelta(minutes=30 + m_i * 10)
                            db.add(
                                MicroScore(
                                    cohort_id=cohort.id,
                                    student_id=student.id,
                                    lesson_id=lesson.id,
                                    competency=micro.competency,
                                    level=LEVEL_ENUM[micro.level],
                                    evidence=micro.evidence,
                                    created_at=ts,
                                    updated_at=ts,
                                )
                            )
                    continue

                level_val = plan.lesson_levels[idx]
                if level_val is SKIP:
                    lesson_level_counts[idx]["nao_concluiu"] += 1
                    continue

                assert level_val is None or isinstance(level_val, str)
                if level_val is None:
                    lesson_level_counts[idx]["sem_evidencia"] += 1
                else:
                    lesson_level_counts[idx][level_val] += 1

                micros = pick_micros(
                    key,
                    level_val,
                    rng,
                    mode=plan.micro_mode,
                    salt=student_ord * 10 + idx,
                )
                for m_i, micro in enumerate(micros):
                    ts = concluded_at + timedelta(minutes=20 + m_i * 12)
                    db.add(
                        MicroScore(
                            cohort_id=cohort.id,
                            student_id=student.id,
                            lesson_id=lesson.id,
                            competency=micro.competency,
                            level=LEVEL_ENUM[micro.level],
                            evidence=micro.evidence,
                            created_at=ts,
                            updated_at=ts,
                        )
                    )

                assessment_body, gaps = lesson_text(
                    key, level_val, rng, salt=student_ord * 17 + idx
                )
                assess_at = concluded_at + timedelta(hours=2, minutes=student_ord % 40)
                db.add(
                    StudentAssessment(
                        cohort_id=cohort.id,
                        student_id=student.id,
                        scope=AssessmentScope.LESSON,
                        lesson_id=lesson.id,
                        module_id=None,
                        track_id=None,
                        level=None if level_val is None else LEVEL_ENUM[level_val],
                        assessment=assessment_body,
                        gaps=gaps,
                        created_at=assess_at,
                        updated_at=assess_at,
                    )
                )

            # Module assessments
            for mod_idx, module in enumerate(modules):
                mod_level = plan.module_levels[mod_idx]
                if mod_level is SKIP:
                    continue
                mod_key = MODULE_TITLE_TO_KEY[module.title]
                # Timestamp after last lesson assessment of that module.
                last_lesson_idx = 2 if mod_idx == 0 else 5
                mod_anchor = (
                    _lesson_anchor(now, last_lesson_idx)
                    + timedelta(days=1, hours=4)
                    + student_hour_offset
                )
                body, gaps = module_text(
                    mod_key, mod_level, rng, salt=student_ord * 31 + mod_idx
                )
                db.add(
                    StudentAssessment(
                        cohort_id=cohort.id,
                        student_id=student.id,
                        scope=AssessmentScope.MODULE,
                        lesson_id=None,
                        module_id=module.id,
                        track_id=None,
                        level=None if mod_level is None else LEVEL_ENUM[mod_level],
                        assessment=body,
                        gaps=gaps,
                        created_at=mod_anchor,
                        updated_at=mod_anchor,
                    )
                )

            # Track assessment
            t_level = plan.track_level
            if t_level is not SKIP:
                assert t_level is None or isinstance(t_level, str)
                track_anchor = (
                    _lesson_anchor(now, 5)
                    + timedelta(days=2, hours=6)
                    + student_hour_offset
                )
                body, gaps = track_text(t_level, rng, salt=student_ord * 41)
                db.add(
                    StudentAssessment(
                        cohort_id=cohort.id,
                        student_id=student.id,
                        scope=AssessmentScope.TRACK,
                        lesson_id=None,
                        module_id=None,
                        track_id=track.id,
                        level=None if t_level is None else LEVEL_ENUM[t_level],
                        assessment=body,
                        gaps=gaps,
                        created_at=track_anchor,
                        updated_at=track_anchor,
                    )
                )

        await db.commit()

        _print_summary(
            track_title=track.title,
            students=students_meta,
            plans=plans,
            lessons=lessons,
            lesson_level_counts=lesson_level_counts,
        )
