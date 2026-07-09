import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.cohort import Cohort, CohortModuleProfessor, CohortProgress, Enrollment
from app.models.track import Lesson, Module, Track
from app.models.user import Role, User
from app.schemas import (
    CohortCreate,
    CohortDetailOut,
    CohortLessonNoteOut,
    CohortListOut,
    CohortOut,
    CohortProgressOut,
    CohortUpdate,
    EnrollmentCreate,
    EnrollmentBulkCreate,
    EnrollmentBulkOut,
    EnrollmentOut,
    ModuleProfessorIn,
    ModuleProfessorOut,
    TrackOut,
    TranscriptionOut,
)
from app.models.assessment import CohortLessonNote
from app.services.lesson_completion_service import complete_lesson
from app.services.storage.download import file_response
from app.services.transcription_service import transcribe_audio
from app.services.upload_validation import (
    AUDIO_MAX_BYTES,
    is_audio_content_type,
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
        .order_by(Module.position)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ModuleProfessorOut(
            module_id=assignment.module_id,
            module_title=module_title,
            professor_id=assignment.professor_id,
            professor_name=professor_name,
        )
        for assignment, module_title, professor_name in rows
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
    track_id: uuid.UUID,
    assignments: list[ModuleProfessorIn],
) -> None:
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
            "Informe um professor para cada módulo ativo da trilha",
        )

    for item in assignments:
        module = await db.get(Module, item.module_id)
        if module is None or module.track_id != track_id or not module.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Módulo inválido para a trilha")

        professor = await db.get(User, item.professor_id)
        if professor is None or professor.role != Role.PROFESSOR:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Professor inválido")


async def _replace_module_professors(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    assignments: list[ModuleProfessorIn],
) -> None:
    await db.execute(
        delete(CohortModuleProfessor).where(CohortModuleProfessor.cohort_id == cohort_id)
    )
    for item in assignments:
        db.add(
            CohortModuleProfessor(
                cohort_id=cohort_id,
                module_id=item.module_id,
                professor_id=item.professor_id,
            )
        )
    await db.flush()


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


async def _assert_lesson_professor(
    db: AsyncSession, user: User, cohort: Cohort, lesson_id: uuid.UUID
) -> None:
    if user.role != Role.PROFESSOR:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Só o professor do módulo pode realizar esta ação",
        )

    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")

    assigned = await db.scalar(
        select(CohortModuleProfessor.id).where(
            CohortModuleProfessor.cohort_id == cohort.id,
            CohortModuleProfessor.module_id == lesson.module_id,
            CohortModuleProfessor.professor_id == user.id,
        )
    )
    if assigned is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Só o professor deste módulo pode realizar esta ação",
        )


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


async def _current_lesson_id(db: AsyncSession, cohort: Cohort) -> uuid.UUID | None:
    completed = set(
        (
            await db.execute(
                select(CohortProgress.lesson_id).where(CohortProgress.cohort_id == cohort.id)
            )
        ).scalars().all()
    )
    track = await db.scalar(
        select(Track)
        .where(Track.id == cohort.track_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    if track is None:
        return None

    for mod in sorted(track.modules, key=lambda m: m.position):
        if not mod.is_active:
            continue
        for lesson in sorted(mod.lessons, key=lambda l: l.position):
            if not lesson.is_active:
                continue
            if lesson.id not in completed:
                return lesson.id
    return None


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

    await _validate_module_professors(db, body.track_id, body.module_professors)

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
        await _validate_module_professors(db, cohort.track_id, body.module_professors)
        await _replace_module_professors(db, cohort.id, body.module_professors)

    if body.name is not None:
        cohort.name = body.name

    await db.flush()
    return await _cohort_detail(db, cohort)


@router.get(
    "/{cohort_id}/enrollments",
    response_model=list[EnrollmentOut],
    dependencies=[Depends(can_manage)],
)
async def list_enrollments(
    cohort_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    await _get_cohort_or_404(db, cohort_id)
    stmt = (
        select(Enrollment, User.name, User.email, User.whatsapp)
        .join(User, Enrollment.student_id == User.id)
        .where(Enrollment.cohort_id == cohort_id)
        .order_by(User.name)
    )
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
    await _get_cohort_or_404(db, cohort_id)

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
    await _get_cohort_or_404(db, cohort_id)

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
    await db.flush()


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

    completed = list(
        (
            await db.execute(
                select(CohortProgress.lesson_id).where(CohortProgress.cohort_id == cohort_id)
            )
        ).scalars().all()
    )
    return CohortProgressOut(
        completed_lesson_ids=completed,
        current_lesson_id=await _current_lesson_id(db, cohort),
    )


async def _latest_lesson_note(
    db: AsyncSession, cohort_id: uuid.UUID, lesson_id: uuid.UUID
) -> CohortLessonNote | None:
    return await db.scalar(
        select(CohortLessonNote)
        .where(
            CohortLessonNote.cohort_id == cohort_id,
            CohortLessonNote.lesson_id == lesson_id,
        )
        .order_by(CohortLessonNote.created_at.desc())
        .limit(1)
    )


@router.get(
    "/{cohort_id}/lesson-notes",
    response_model=list[CohortLessonNoteOut],
    dependencies=[Depends(can_view)],
)
async def list_lesson_notes(
    cohort_id: uuid.UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    """Metadata of professor reports (attachment/audio) for completed lessons."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)

    notes = (
        await db.execute(
            select(CohortLessonNote)
            .where(CohortLessonNote.cohort_id == cohort_id)
            .order_by(CohortLessonNote.created_at.desc())
        )
    ).scalars().all()

    # One entry per lesson (latest note wins).
    by_lesson: dict[uuid.UUID, CohortLessonNote] = {}
    for note in notes:
        if note.lesson_id not in by_lesson:
            by_lesson[note.lesson_id] = note

    return [
        CohortLessonNoteOut(
            lesson_id=note.lesson_id,
            attachment_filename=note.attachment_filename,
            has_attachment=bool(note.attachment_storage_key),
            has_audio=bool(note.audio_storage_key),
        )
        for note in by_lesson.values()
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
):
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)
    note = await _latest_lesson_note(db, cohort_id, lesson_id)
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
):
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_cohort_access(db, user, cohort)
    note = await _latest_lesson_note(db, cohort_id, lesson_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relato não encontrado")
    return await file_response(
        storage_key=note.audio_storage_key,
        filename="relato-aula.webm",
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
    await _assert_lesson_professor(db, user, cohort, lesson_id)

    if not is_audio_content_type(audio.content_type):
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
):
    """The professor signals the cohort studied the lesson. Advances the cohort and
    unlocks context. Optionally stores docx/txt + recorded audio for compliance."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _assert_lesson_professor(db, user, cohort, lesson_id)

    current = await _current_lesson_id(db, cohort)
    if current is not None and lesson_id != current:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Só é possível encerrar a aula atual da turma",
        )

    stored_attachment = await parse_report_attachment(attachment)
    stored_audio = await parse_report_audio(audio)

    try:
        note = await complete_lesson(
            db,
            cohort_id,
            lesson_id,
            transcript,
            attachment=stored_attachment,
            audio=stored_audio,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

    return {
        "status": "aula encerrada, turma avançada",
        "summary": note.summary,
        "unclear_points": note.unclear_points,
    }
