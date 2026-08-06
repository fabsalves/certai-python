import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.cohort import (
    Cohort,
    CohortModuleProfessor,
    CohortModuleStudent,
    CohortProgress,
    Enrollment,
)
from app.models.track import Lesson, Module, Track
from app.models.user import Role, User
from app.schemas import (
    CohortCreate,
    CohortDetailOut,
    CohortLessonNoteOut,
    CohortListOut,
    CohortOut,
    CohortProgressOut,
    CohortTrackLevelOut,
    CohortTrackLevelsOut,
    CohortUpdate,
    EnrollmentCreate,
    EnrollmentBulkCreate,
    EnrollmentBulkOut,
    EnrollmentOut,
    LessonAssessmentsOut,
    LessonClassesOut,
    LessonClassStatusOut,
    ModuleProfessorIn,
    ModuleProfessorOut,
    PendingAssessmentStudentOut,
    ClaimClassStudentIn,
    UnassignedStudentOut,
    StudentAssessmentOut,
    StudentAssessmentsOut,
    TrackOut,
    TranscriptionOut,
)
from app.models.assessment import CohortLessonNote
from app.services.assessment.read_service import (
    AssessmentReadRow,
    StudentAssessmentReadService,
)
from app.services.cohort import ModuleClassService
from app.services.cohort.mid_join_service import MidJoinService
from app.services.lesson_completion_service import complete_lesson
from app.services.storage.download import file_response
from app.services.track_structure import ordered_active_lessons
from app.services.transcription_service import transcribe_audio
from app.services.upload_validation import (
    AUDIO_MAX_BYTES,
    is_allowed_report_audio,
    parse_report_attachment,
    parse_report_audio,
)

router = APIRouter(prefix="/cohorts", tags=["cohorts"])

can_manage = require_roles(Role.ADMIN, Role.DESIGNER)
can_view = require_roles(Role.ADMIN, Role.DESIGNER, Role.PROFESSOR)


async def _get_cohort_or_404(db: AsyncSession, cohort_id: uuid.UUID) -> Cohort:
    cohort = await db.get(Cohort, cohort_id)
    if cohort is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turma não encontrada")
    return cohort


async def _load_module_professors(
    db: AsyncSession, cohort_id: uuid.UUID
) -> list[ModuleProfessorOut]:
    stmt = (
        select(CohortModuleProfessor, Module.title, User.name)
        .join(Module, CohortModuleProfessor.module_id == Module.id)
        .join(User, CohortModuleProfessor.professor_id == User.id)
        .where(CohortModuleProfessor.cohort_id == cohort_id)
        .order_by(Module.position, User.name)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    roster_rows = (
        await db.execute(
            select(CohortModuleStudent.module_professor_id, CohortModuleStudent.student_id)
            .where(
                CohortModuleStudent.module_professor_id.in_(
                    [module_class.id for module_class, _title, _name in rows]
                )
            )
        )
    ).all()
    roster: dict[uuid.UUID, list[uuid.UUID]] = {}
    for module_professor_id, student_id in roster_rows:
        roster.setdefault(module_professor_id, []).append(student_id)

    return [
        ModuleProfessorOut(
            id=module_class.id,
            module_id=module_class.module_id,
            module_title=module_title,
            professor_id=module_class.professor_id,
            professor_name=professor_name,
            student_ids=roster.get(module_class.id, []),
        )
        for module_class, module_title, professor_name in rows
    ]


async def _active_track_modules(db: AsyncSession, track_id: uuid.UUID) -> list[Module]:
    return list(
        (
            await db.execute(
                select(Module)
                .where(Module.track_id == track_id, Module.is_active.is_(True))
                .order_by(Module.position)
            )
        ).scalars().all()
    )


async def _validate_module_professors(
    db: AsyncSession,
    cohort_id: uuid.UUID | None,
    track_id: uuid.UUID,
    assignments: list[ModuleProfessorIn],
) -> None:
    """Every active module needs at least one professor. A module may have
    several, and then each student belongs to a single one of them."""
    active_modules = await _active_track_modules(db, track_id)
    active_module_ids = {module.id for module in active_modules}

    if not active_modules:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "A trilha não possui módulos ativos",
        )

    assigned_module_ids = {item.module_id for item in assignments}
    if assigned_module_ids != active_module_ids:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Informe ao menos um professor para cada módulo ativo da trilha",
        )

    seen_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for item in assignments:
        module = await db.get(Module, item.module_id)
        if module is None or module.track_id != track_id or not module.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Módulo inválido para a trilha")

        professor = await db.get(User, item.professor_id)
        if professor is None or professor.role != Role.PROFESSOR:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Professor inválido")

        pair = (item.module_id, item.professor_id)
        if pair in seen_pairs:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "O mesmo professor foi informado duas vezes no mesmo módulo",
            )
        seen_pairs.add(pair)

    await _validate_module_rosters(db, cohort_id, assignments)


async def _validate_module_rosters(
    db: AsyncSession,
    cohort_id: uuid.UUID | None,
    assignments: list[ModuleProfessorIn],
) -> None:
    """Rosters may only list enrolled students, and a student belongs to one
    class per module. Full coverage is not required here -- students enrolled
    later are caught by the guard at lesson completion."""
    by_module: dict[uuid.UUID, list[ModuleProfessorIn]] = {}
    for item in assignments:
        by_module.setdefault(item.module_id, []).append(item)

    enrolled: set[uuid.UUID] = set()
    if cohort_id is not None:
        enrolled = set(
            (
                await db.scalars(
                    select(Enrollment.student_id).where(Enrollment.cohort_id == cohort_id)
                )
            ).all()
        )

    for items in by_module.values():
        if len(items) < 2:
            continue

        seen_students: set[uuid.UUID] = set()
        for item in items:
            for student_id in item.student_ids:
                if student_id not in enrolled:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        "A divisão inclui um aluno que não está matriculado na turma",
                    )
                if student_id in seen_students:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        "Um aluno foi atribuído a mais de um professor no mesmo módulo",
                    )
                seen_students.add(student_id)


async def _replace_module_professors(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    assignments: list[ModuleProfessorIn],
) -> None:
    """Reconcile the cohort's classes. Existing ones are kept so their progress
    and reports survive; a class that already taught cannot be removed."""
    existing = list(
        (
            await db.scalars(
                select(CohortModuleProfessor).where(
                    CohortModuleProfessor.cohort_id == cohort_id
                )
            )
        ).all()
    )
    existing_by_pair = {
        (item.module_id, item.professor_id): item for item in existing
    }
    wanted_pairs = {(item.module_id, item.professor_id) for item in assignments}

    for pair, module_class in existing_by_pair.items():
        if pair in wanted_pairs:
            continue
        if await _class_has_history(db, module_class.id):
            professor = await db.get(User, module_class.professor_id)
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{professor.name if professor else 'O professor'} já encerrou aulas "
                "neste módulo e não pode ser removido",
            )
        await db.delete(module_class)
    await db.flush()

    by_module: dict[uuid.UUID, list[tuple[CohortModuleProfessor, ModuleProfessorIn]]] = {}
    for item in assignments:
        module_class = existing_by_pair.get((item.module_id, item.professor_id))
        if module_class is None:
            module_class = CohortModuleProfessor(
                cohort_id=cohort_id,
                module_id=item.module_id,
                professor_id=item.professor_id,
            )
            db.add(module_class)
        by_module.setdefault(item.module_id, []).append((module_class, item))
    await db.flush()

    cohort = await db.get(Cohort, cohort_id)
    if cohort is None:
        return

    additions: list[tuple[CohortModuleProfessor, uuid.UUID]] = []
    for module_classes in by_module.values():
        additions.extend(
            await ModuleClassService.replace_module_roster(
                db,
                [module_class for module_class, _item in module_classes],
                {
                    module_class.id: item.student_ids
                    for module_class, item in module_classes
                },
            )
        )
    await MidJoinService.catch_up_roster_additions(db, cohort, additions)


async def _class_has_history(db: AsyncSession, module_professor_id: uuid.UUID) -> bool:
    progress = await db.scalar(
        select(CohortProgress.id).where(
            CohortProgress.module_professor_id == module_professor_id
        )
    )
    if progress is not None:
        return True
    note = await db.scalar(
        select(CohortLessonNote.id).where(
            CohortLessonNote.module_professor_id == module_professor_id
        )
    )
    return note is not None


async def _assert_cohort_access(
    db: AsyncSession, user: User, cohort: Cohort
) -> None:
    if user.role != Role.PROFESSOR:
        return

    assigned = await db.scalar(
        select(CohortModuleProfessor.id).where(
            CohortModuleProfessor.cohort_id == cohort.id,
            CohortModuleProfessor.professor_id == user.id,
        )
    )
    if assigned is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não leciona nesta turma")


async def _visible_student_ids(
    db: AsyncSession, user: User, cohort: Cohort
) -> set[uuid.UUID] | None:
    """Students a professor may see: the ones in their own classes. None means
    no restriction (admin and designer see the whole cohort)."""
    if user.role != Role.PROFESSOR:
        return None

    classes = await ModuleClassService.classes_of_professor(db, cohort.id, user.id)
    visible: set[uuid.UUID] = set()
    for module_class in classes:
        visible.update(await ModuleClassService.student_ids_of(db, module_class))
    return visible


async def _visible_student_ids_for_lesson(
    db: AsyncSession, user: User, cohort: Cohort, lesson_id: uuid.UUID
) -> set[uuid.UUID] | None:
    """Students visible for one lesson's assessments.

    Cohort-wide union is wrong here: a professor who teaches the whole cohort
    in module B must not see module A's other class when opening a lesson of A.
    Admins/designers keep unrestricted access (None).
    """
    if user.role != Role.PROFESSOR:
        return None

    module_class = await _lesson_class_of_professor(db, user, cohort, lesson_id)
    return set(await ModuleClassService.student_ids_of(db, module_class))


async def _lesson_class_of_professor(
    db: AsyncSession, user: User, cohort: Cohort, lesson_id: uuid.UUID
) -> CohortModuleProfessor:
    """The professor's own class for this lesson's module. 403 when they do not
    teach it -- the single authorization point for acting on a lesson."""
    if user.role != Role.PROFESSOR:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Só o professor do módulo pode realizar esta ação",
        )

    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")

    module_class = await ModuleClassService.class_of_professor(
        db, cohort.id, lesson.module_id, user.id
    )
    if module_class is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Só o professor deste módulo pode realizar esta ação",
        )
    return module_class


async def _cohort_detail(db: AsyncSession, cohort: Cohort) -> CohortDetailOut:
    track_title = await db.scalar(select(Track.title).where(Track.id == cohort.track_id))
    enrollment_count = await db.scalar(
        select(func.count()).select_from(Enrollment).where(Enrollment.cohort_id == cohort.id)
    )
    return CohortDetailOut(
        id=cohort.id,
        name=cohort.name,
        track_id=cohort.track_id,
        track_title=track_title or "",
        enrollment_count=enrollment_count or 0,
        module_professors=await _load_module_professors(db, cohort.id),
    )


async def _next_lesson_for_class(
    db: AsyncSession, cohort: Cohort, module_class: CohortModuleProfessor
) -> uuid.UUID | None:
    """The lesson this class is due to close: the first active lesson of its own
    module that it has not closed yet. Classes of the same module advance
    independently, so a professor who postponed is never blocked by another."""
    return await MidJoinService.next_open_lesson_id(db, cohort, module_class)


async def _lesson_closings(
    db: AsyncSession, cohort: Cohort, ordered: list[Lesson]
) -> dict[uuid.UUID, list[LessonClassStatusOut]]:
    """Per lesson, how each class responsible for it stands."""
    class_rows = (
        await db.execute(
            select(CohortModuleProfessor, User.name)
            .join(User, CohortModuleProfessor.professor_id == User.id)
            .where(CohortModuleProfessor.cohort_id == cohort.id)
            .order_by(User.name)
        )
    ).all()
    classes_by_module: dict[uuid.UUID, list[tuple[CohortModuleProfessor, str]]] = {}
    for module_class, professor_name in class_rows:
        classes_by_module.setdefault(module_class.module_id, []).append(
            (module_class, professor_name)
        )

    progress_rows = (
        await db.execute(
            select(
                CohortProgress.lesson_id,
                CohortProgress.module_professor_id,
                CohortProgress.created_at,
            ).where(CohortProgress.cohort_id == cohort.id)
        )
    ).all()
    closed_at: dict[tuple[uuid.UUID, uuid.UUID], datetime] = {
        (lesson_id, module_professor_id): created_at
        for lesson_id, module_professor_id, created_at in progress_rows
    }

    return {
        lesson.id: [
            LessonClassStatusOut(
                module_professor_id=module_class.id,
                professor_id=module_class.professor_id,
                professor_name=professor_name,
                closed=(lesson.id, module_class.id) in closed_at,
                closed_at=closed_at.get((lesson.id, module_class.id)),
            )
            for module_class, professor_name in classes_by_module.get(
                lesson.module_id, []
            )
        ]
        for lesson in ordered
    }


@router.get("", response_model=list[CohortListOut], dependencies=[Depends(can_view)])
async def list_cohorts(user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    enrollment_count = (
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.cohort_id == Cohort.id)
        .correlate(Cohort)
        .scalar_subquery()
    )
    stmt = select(Cohort, Track.title, enrollment_count).join(
        Track, Cohort.track_id == Track.id
    )
    if user.role == Role.PROFESSOR:
        stmt = stmt.where(
            Cohort.id.in_(
                select(CohortModuleProfessor.cohort_id).where(
                    CohortModuleProfessor.professor_id == user.id
                )
            )
        )

    rows = (await db.execute(stmt)).all()
    result: list[CohortListOut] = []
    for cohort, track_title, count in rows:
        result.append(
            CohortListOut(
                id=cohort.id,
                name=cohort.name,
                track_id=cohort.track_id,
                track_title=track_title,
                enrollment_count=count or 0,
                module_professors=await _load_module_professors(db, cohort.id),
            )
        )
    return result


@router.get("/{cohort_id}", response_model=CohortDetailOut, dependencies=[Depends(can_view)])
async def get_cohort(
    cohort_id: uuid.UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)
    return await _cohort_detail(db, cohort)


@router.post("", response_model=CohortOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(can_manage)])
async def create_cohort(body: CohortCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    track = await db.get(Track, body.track_id)
    if track is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trilha não encontrada")
    if not track.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Trilha desativada")

    await _validate_module_professors(db, None, body.track_id, body.module_professors)

    cohort = Cohort(name=body.name, track_id=body.track_id)
    db.add(cohort)
    await db.flush()
    await _replace_module_professors(db, cohort.id, body.module_professors)
    return cohort


@router.patch("/{cohort_id}", response_model=CohortDetailOut, dependencies=[Depends(can_manage)])
async def update_cohort(
    cohort_id: uuid.UUID,
    body: CohortUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cohort = await _get_cohort_or_404(db, cohort_id)

    if body.module_professors is not None:
        await _validate_module_professors(
            db, cohort.id, cohort.track_id, body.module_professors
        )
        await _replace_module_professors(db, cohort.id, body.module_professors)

    if body.name is not None:
        cohort.name = body.name

    await db.flush()
    return await _cohort_detail(db, cohort)


@router.get(
    "/{cohort_id}/enrollments",
    response_model=list[EnrollmentOut],
    dependencies=[Depends(can_view)],
)
async def list_enrollments(
    cohort_id: uuid.UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)
    stmt = (
        select(Enrollment, User.name, User.email, User.whatsapp)
        .join(User, Enrollment.student_id == User.id)
        .where(Enrollment.cohort_id == cohort_id)
        .order_by(User.name)
    )
    visible = await _visible_student_ids(db, user, cohort)
    if visible is not None:
        stmt = stmt.where(Enrollment.student_id.in_(visible))
    rows = (await db.execute(stmt)).all()
    return [
        EnrollmentOut(
            id=enrollment.id,
            student_id=enrollment.student_id,
            student_name=student_name,
            student_email=student_email,
            student_whatsapp=student_whatsapp,
            enrolled_at=enrollment.created_at,
        )
        for enrollment, student_name, student_email, student_whatsapp in rows
    ]


@router.post("/{cohort_id}/enrollments", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(can_manage)])
async def enroll(
    cohort_id: uuid.UUID, body: EnrollmentCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    cohort = await _get_cohort_or_404(db, cohort_id)

    student = await db.get(User, body.student_id)
    if student is None or student.role != Role.STUDENT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aluno inválido")

    exists = await db.scalar(
        select(Enrollment.id).where(
            Enrollment.cohort_id == cohort_id, Enrollment.student_id == body.student_id
        )
    )
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Aluno já matriculado nesta turma")

    enrollment = Enrollment(cohort_id=cohort_id, student_id=body.student_id)
    db.add(enrollment)
    await db.flush()
    await MidJoinService.catch_up_on_enroll(db, cohort, [body.student_id])
    return {"status": "matriculado"}


@router.post(
    "/{cohort_id}/enrollments/bulk",
    response_model=EnrollmentBulkOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def enroll_bulk(
    cohort_id: uuid.UUID,
    body: EnrollmentBulkCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cohort = await _get_cohort_or_404(db, cohort_id)

    unique_ids = list(dict.fromkeys(body.student_ids))
    if not unique_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe ao menos um aluno")

    students = (
        await db.execute(
            select(User.id).where(User.id.in_(unique_ids), User.role == Role.STUDENT)
        )
    ).scalars().all()
    if len(students) != len(unique_ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Um ou mais alunos são inválidos")

    already_enrolled = set(
        (
            await db.execute(
                select(Enrollment.student_id).where(
                    Enrollment.cohort_id == cohort_id,
                    Enrollment.student_id.in_(unique_ids),
                )
            )
        ).scalars().all()
    )

    to_enroll = [student_id for student_id in unique_ids if student_id not in already_enrolled]
    for student_id in to_enroll:
        db.add(Enrollment(cohort_id=cohort_id, student_id=student_id))

    await db.flush()
    await MidJoinService.catch_up_on_enroll(db, cohort, to_enroll)
    return EnrollmentBulkOut(
        enrolled_count=len(to_enroll),
        skipped_count=len(already_enrolled),
    )


@router.delete(
    "/{cohort_id}/enrollments/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(can_manage)],
)
async def unenroll(
    cohort_id: uuid.UUID, student_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    enrollment = await db.scalar(
        select(Enrollment).where(
            Enrollment.cohort_id == cohort_id, Enrollment.student_id == student_id
        )
    )
    if enrollment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Matrícula não encontrada")
    await db.delete(enrollment)
    # Leaving the cohort also leaves every class of it.
    await db.execute(
        delete(CohortModuleStudent).where(
            CohortModuleStudent.student_id == student_id,
            CohortModuleStudent.module_professor_id.in_(
                select(CohortModuleProfessor.id).where(
                    CohortModuleProfessor.cohort_id == cohort_id
                )
            ),
        )
    )
    await db.flush()


@router.get(
    "/{cohort_id}/modules/{module_id}/unassigned-students",
    response_model=list[UnassignedStudentOut],
    dependencies=[Depends(can_view)],
)
async def list_unassigned_students(
    cohort_id: uuid.UUID,
    module_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Enrolled students with no class in a split module."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)

    if user.role == Role.PROFESSOR:
        teaches = await ModuleClassService.class_of_professor(
            db, cohort.id, module_id, user.id
        )
        if teaches is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Você não leciona este módulo"
            )

    unassigned_ids = await ModuleClassService.unassigned_student_ids(
        db, cohort_id, module_id
    )
    if not unassigned_ids:
        return []

    rows = (
        await db.execute(
            select(User.id, User.name, User.email)
            .where(User.id.in_(unassigned_ids))
            .order_by(User.name)
        )
    ).all()
    return [
        UnassignedStudentOut(
            student_id=student_id, student_name=name, student_email=email
        )
        for student_id, name, email in rows
    ]


@router.post(
    "/{cohort_id}/modules/{module_id}/classes/me/students",
    response_model=ModuleProfessorOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(Role.PROFESSOR))],
)
async def claim_class_student(
    cohort_id: uuid.UUID,
    module_id: uuid.UUID,
    body: ClaimClassStudentIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Professor pulls an unassigned student into their own class (mid-track join)."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)

    try:
        module_class = await MidJoinService.claim_student(
            db, cohort, module_id, user.id, body.student_id
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    professors = await _load_module_professors(db, cohort.id)
    for item in professors:
        if item.id == module_class.id:
            return item
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Turma não encontrada")


@router.get(
    "/{cohort_id}/track",
    response_model=TrackOut,
    dependencies=[Depends(can_view)],
)
async def get_cohort_track(
    cohort_id: uuid.UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)
    track = await db.scalar(
        select(Track)
        .where(Track.id == cohort.track_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    if track is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trilha não encontrada")
    return track


@router.get(
    "/{cohort_id}/progress",
    response_model=CohortProgressOut,
    dependencies=[Depends(can_view)],
)
async def get_progress(
    cohort_id: uuid.UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)

    ordered = await ordered_active_lessons(db, cohort.track_id)
    closings = await _lesson_closings(db, cohort, ordered)

    completed: list[uuid.UUID] = []
    partial: list[uuid.UUID] = []
    for lesson in ordered:
        statuses = closings.get(lesson.id, [])
        if not statuses:
            continue
        if all(item.closed for item in statuses):
            completed.append(lesson.id)
        elif any(item.closed for item in statuses):
            partial.append(lesson.id)

    # A class is late when it still owes a lesson that a later one already passed.
    last_closed_index = -1
    for index, lesson in enumerate(ordered):
        if any(item.closed for item in closings.get(lesson.id, [])):
            last_closed_index = index

    lesson_classes = [
        LessonClassesOut(
            lesson_id=lesson.id,
            classes=closings.get(lesson.id, []),
            delayed=(
                index < last_closed_index
                and any(not item.closed for item in closings.get(lesson.id, []))
            ),
        )
        for index, lesson in enumerate(ordered)
    ]

    current_lesson_id = await _requester_current_lesson_id(
        db, user, cohort, ordered, closings
    )
    return CohortProgressOut(
        completed_lesson_ids=completed,
        partial_lesson_ids=partial,
        current_lesson_id=current_lesson_id,
        lesson_classes=lesson_classes,
    )


async def _requester_current_lesson_id(
    db: AsyncSession,
    user: User,
    cohort: Cohort,
    ordered: list[Lesson],
    closings: dict[uuid.UUID, list[LessonClassStatusOut]],
) -> uuid.UUID | None:
    """A professor sees the lesson their own class is due to close; everyone
    else sees the first lesson the whole cohort has not finished."""
    if user.role == Role.PROFESSOR:
        own_pending: uuid.UUID | None = None
        teaches_any = False
        for lesson in ordered:
            own = [
                item
                for item in closings.get(lesson.id, [])
                if item.professor_id == user.id
            ]
            if not own:
                continue
            teaches_any = True
            if own_pending is None and not all(item.closed for item in own):
                own_pending = lesson.id
        if teaches_any:
            return own_pending

    for lesson in ordered:
        statuses = closings.get(lesson.id, [])
        if not statuses or not all(item.closed for item in statuses):
            return lesson.id
    return None


def _assessment_out(row: AssessmentReadRow) -> StudentAssessmentOut:
    return StudentAssessmentOut(
        id=row.id,
        student_id=row.student_id,
        student_name=row.student_name,
        scope=row.scope,
        lesson_id=row.lesson_id,
        module_id=row.module_id,
        track_id=row.track_id,
        scope_title=row.scope_title,
        level=row.level,
        assessment=row.assessment,
        gaps=row.gaps,
        created_at=row.created_at,
    )


@router.get(
    "/{cohort_id}/lessons/{lesson_id}/assessments",
    response_model=LessonAssessmentsOut,
    dependencies=[Depends(can_view)],
)
async def list_lesson_assessments(
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Latest lesson assessments for this class, plus concluded students still pending."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)
    try:
        result = await StudentAssessmentReadService.latest_lesson_assessments(
            db,
            cohort_id=cohort_id,
            lesson_id=lesson_id,
            student_ids=await _visible_student_ids_for_lesson(
                db, user, cohort, lesson_id
            ),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return LessonAssessmentsOut(
        lesson_id=result.lesson_id,
        assessments=[_assessment_out(row) for row in result.assessments],
        pending=[
            PendingAssessmentStudentOut(
                student_id=item.student_id,
                student_name=item.student_name,
            )
            for item in result.pending
        ],
    )


@router.get(
    "/{cohort_id}/students/track-levels",
    response_model=CohortTrackLevelsOut,
    dependencies=[Depends(can_view)],
)
async def list_student_track_levels(
    cohort_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Latest track-level assessment summary for every enrolled student (batch)."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)
    try:
        result = await StudentAssessmentReadService.latest_track_levels(
            db,
            cohort_id=cohort_id,
            student_ids=await _visible_student_ids(db, user, cohort),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return CohortTrackLevelsOut(
        students=[
            CohortTrackLevelOut(
                student_id=row.student_id,
                level=row.level,
                has_assessment=row.has_assessment,
            )
            for row in result.students
        ]
    )


@router.get(
    "/{cohort_id}/students/{student_id}/assessments",
    response_model=StudentAssessmentsOut,
    dependencies=[Depends(can_view)],
)
async def list_student_assessments(
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Latest lesson/module/track assessments for one enrolled student."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)

    visible = await _visible_student_ids(db, user, cohort)
    if visible is not None and student_id not in visible:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Este aluno não está em nenhuma turma sua"
        )
    try:
        result = await StudentAssessmentReadService.latest_for_student(
            db, cohort_id=cohort_id, student_id=student_id
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return StudentAssessmentsOut(
        student_id=result.student_id,
        student_name=result.student_name,
        assessments=[_assessment_out(row) for row in result.assessments],
    )


async def _latest_lesson_note(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    module_professor_id: uuid.UUID | None = None,
) -> CohortLessonNote | None:
    """Latest report for a lesson. Scoped to one class when given -- two
    professors teaching the same lesson keep separate reports."""
    stmt = select(CohortLessonNote).where(
        CohortLessonNote.cohort_id == cohort_id,
        CohortLessonNote.lesson_id == lesson_id,
    )
    if module_professor_id is not None:
        stmt = stmt.where(CohortLessonNote.module_professor_id == module_professor_id)
    return await db.scalar(
        stmt.order_by(CohortLessonNote.created_at.desc()).limit(1)
    )


async def _resolve_note_class_id(
    db: AsyncSession,
    user: User,
    cohort: Cohort,
    lesson_id: uuid.UUID,
    module_professor_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Which class's report the requester is asking for. A professor always gets
    their own; admins and designers may name one explicitly."""
    if user.role == Role.PROFESSOR:
        module_class = await _lesson_class_of_professor(db, user, cohort, lesson_id)
        return module_class.id
    return module_professor_id


@router.get(
    "/{cohort_id}/lesson-notes",
    response_model=list[CohortLessonNoteOut],
    dependencies=[Depends(can_view)],
)
async def list_lesson_notes(
    cohort_id: uuid.UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    """Metadata of professor reports (attachment/audio), one per lesson and class."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)

    stmt = (
        select(CohortLessonNote, CohortModuleProfessor.professor_id, User.name)
        .join(
            CohortModuleProfessor,
            CohortLessonNote.module_professor_id == CohortModuleProfessor.id,
        )
        .join(User, CohortModuleProfessor.professor_id == User.id)
        .where(CohortLessonNote.cohort_id == cohort_id)
        .order_by(CohortLessonNote.created_at.desc())
    )
    if user.role == Role.PROFESSOR:
        stmt = stmt.where(CohortModuleProfessor.professor_id == user.id)
    rows = (await db.execute(stmt)).all()

    # One entry per lesson and class (latest note wins).
    latest: dict[tuple[uuid.UUID, uuid.UUID], tuple[CohortLessonNote, uuid.UUID, str]] = {}
    for note, professor_id, professor_name in rows:
        key = (note.lesson_id, note.module_professor_id)
        if key not in latest:
            latest[key] = (note, professor_id, professor_name)

    return [
        CohortLessonNoteOut(
            lesson_id=note.lesson_id,
            module_professor_id=note.module_professor_id,
            professor_id=professor_id,
            professor_name=professor_name,
            attachment_filename=note.attachment_filename,
            has_attachment=bool(note.attachment_storage_key),
            has_audio=bool(note.audio_storage_key),
            audio_filename=note.audio_filename,
            audio_source=note.audio_source,
            ingestion_status=note.ingestion_status,
        )
        for note, professor_id, professor_name in latest.values()
    ]


@router.get(
    "/{cohort_id}/lessons/{lesson_id}/attachment",
    dependencies=[Depends(can_view)],
)
async def download_lesson_attachment(
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    module_professor_id: Annotated[uuid.UUID | None, Query()] = None,
):
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)
    class_id = await _resolve_note_class_id(
        db, user, cohort, lesson_id, module_professor_id
    )
    note = await _latest_lesson_note(db, cohort_id, lesson_id, class_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relato não encontrado")
    return await file_response(
        storage_key=note.attachment_storage_key,
        filename=note.attachment_filename or "anexo",
        content_type=note.attachment_content_type,
    )


@router.get(
    "/{cohort_id}/lessons/{lesson_id}/audio",
    dependencies=[Depends(can_view)],
)
async def download_lesson_audio(
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    module_professor_id: Annotated[uuid.UUID | None, Query()] = None,
):
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)
    class_id = await _resolve_note_class_id(
        db, user, cohort, lesson_id, module_professor_id
    )
    note = await _latest_lesson_note(db, cohort_id, lesson_id, class_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relato não encontrado")
    return await file_response(
        storage_key=note.audio_storage_key,
        filename=note.audio_filename or "relato-aula.webm",
        content_type=note.audio_content_type or "audio/webm",
    )


@router.post("/{cohort_id}/transcribe-report", response_model=TranscriptionOut)
async def transcribe_lesson_report(
    cohort_id: uuid.UUID,
    lesson_id: Annotated[uuid.UUID, Query(description="Aula do relato")],
    user: Annotated[CurrentUser, Depends(require_roles(Role.PROFESSOR))],
    db: Annotated[AsyncSession, Depends(get_db)],
    audio: Annotated[UploadFile, File(description="Áudio do relato da aula")],
):
    """Transcreve o áudio do professor via Groq. O texto retorna para revisão antes do envio."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _lesson_class_of_professor(db, user, cohort, lesson_id)

    if not is_allowed_report_audio(audio.content_type, audio.filename):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo deve ser de áudio")

    content = await audio.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Áudio vazio")
    if len(content) > AUDIO_MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Áudio muito grande (máx. 25 MB)")

    filename = audio.filename or "report.webm"
    try:
        text = await transcribe_audio(content, filename=filename)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_UNAVAILABLE, str(e)) from e
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Não foi possível transcrever o áudio. Tente novamente.",
        ) from e

    return TranscriptionOut(transcript=text)


@router.post("/{cohort_id}/complete-lesson")
async def complete(
    cohort_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_roles(Role.PROFESSOR))],
    db: Annotated[AsyncSession, Depends(get_db)],
    lesson_id: Annotated[uuid.UUID, Form(description="Aula a encerrar")],
    transcript: Annotated[str, Form()] = "",
    attachment: Annotated[UploadFile | None, File()] = None,
    audio: Annotated[UploadFile | None, File()] = None,
    audio_source: Annotated[str, Form()] = "",
):
    """The professor signals their own class studied the lesson. Advances that
    class and unlocks its context. The AI ingestion (and only then the WhatsApp
    dispatch) runs asynchronously after this request commits."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    module_class = await _lesson_class_of_professor(db, user, cohort, lesson_id)

    unassigned = await ModuleClassService.unassigned_student_ids(
        db, cohort_id, module_class.module_id
    )
    if unassigned:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{len(unassigned)} aluno(s) da turma ainda não foram divididos entre os "
            "professores deste módulo. Vincule-os à sua turma no Andamento ou peça ao "
            "coordenador para concluir a divisão.",
        )

    current = await _next_lesson_for_class(db, cohort, module_class)
    if current is not None and lesson_id != current:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Só é possível encerrar a aula atual da sua turma",
        )

    stored_attachment = await parse_report_attachment(attachment)
    stored_audio = await parse_report_audio(audio)

    try:
        note = await complete_lesson(
            db,
            cohort_id,
            lesson_id,
            transcript,
            module_professor_id=module_class.id,
            attachment=stored_attachment,
            audio=stored_audio,
            audio_source=audio_source or None,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

    return {
        "status": "aula encerrada, turma avançada",
        "ingestion_status": note.ingestion_status,
    }


@router.post("/{cohort_id}/lessons/{lesson_id}/reingest")
async def reingest_lesson_note(
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_roles(Role.PROFESSOR))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Re-enqueue the AI ingestion of a failed lesson report. On completion the
    task chains the WhatsApp dispatch that was held back."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    module_class = await _lesson_class_of_professor(db, user, cohort, lesson_id)

    note = await _latest_lesson_note(db, cohort_id, lesson_id, module_class.id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relato não encontrado")
    if note.ingestion_status != "failed":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Só é possível reprocessar relatos com falha na ingestão",
        )

    note.ingestion_status = "pending"
    await db.flush()

    from app.core.db_events import enqueue_after_commit
    from app.workers.tasks import ingest_lesson_completion

    enqueue_after_commit(db, ingest_lesson_completion, str(note.id))
    return {"status": "reprocessamento enfileirado", "ingestion_status": note.ingestion_status}
