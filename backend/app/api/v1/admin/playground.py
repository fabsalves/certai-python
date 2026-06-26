import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.cohort import Cohort, CohortModuleProfessor, CohortProgress, Enrollment
from app.models.conversation import Conversation, Message
from app.models.track import Lesson
from app.models.user import Role, User
from app.schemas import (
    AgentResponse,
    LessonCompletionIn,
    MessageIn,
    MessageOut,
    TranscriptionOut,
)
from app.services.conversation_service import student_lesson_message
from app.services.lesson_completion_service import complete_lesson
from app.services.transcription_service import transcribe_audio

router = APIRouter(prefix="/admin/playground", tags=["admin-playground"])

admin_only = require_roles(Role.ADMIN)


async def _get_cohort_or_404(db: AsyncSession, cohort_id: uuid.UUID) -> Cohort:
    cohort = await db.get(Cohort, cohort_id)
    if cohort is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turma não encontrada")
    return cohort


async def _ensure_enrolled_student(
    db: AsyncSession, cohort_id: uuid.UUID, student_id: uuid.UUID
) -> User:
    student = await db.get(User, student_id)
    if student is None or student.role != Role.STUDENT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aluno inválido")

    enrolled = await db.scalar(
        select(Enrollment.id).where(
            Enrollment.cohort_id == cohort_id,
            Enrollment.student_id == student_id,
        )
    )
    if enrolled is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "O aluno selecionado não está matriculado nesta turma",
        )
    return student


async def _ensure_module_professor(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    professor_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> User:
    professor = await db.get(User, professor_id)
    if professor is None or professor.role != Role.PROFESSOR:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Professor inválido")

    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")

    assigned = await db.scalar(
        select(CohortModuleProfessor.id).where(
            CohortModuleProfessor.cohort_id == cohort_id,
            CohortModuleProfessor.module_id == lesson.module_id,
            CohortModuleProfessor.professor_id == professor_id,
        )
    )
    if assigned is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "O professor selecionado não leciona o módulo desta aula",
        )
    return professor


async def _current_lesson_id(db: AsyncSession, cohort: Cohort) -> uuid.UUID | None:
    from sqlalchemy.orm import selectinload

    from app.models.track import Module, Track

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


@router.get(
    "/cohorts/{cohort_id}/students/{student_id}/lessons/{lesson_id}/messages",
    response_model=list[MessageOut],
)
async def list_student_messages(
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: Annotated[User, Depends(admin_only)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Histórico da conversa do aluno na aula — somente admin."""
    await _get_cohort_or_404(db, cohort_id)
    await _ensure_enrolled_student(db, cohort_id, student_id)

    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.cohort_id == cohort_id,
            Conversation.user_id == student_id,
            Conversation.lesson_id == lesson_id,
        )
    )
    if conversation is None:
        return []

    messages = (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
    ).all()
    return [
        MessageOut(author=m.author.value, content=m.content, created_at=m.created_at)
        for m in messages
    ]


@router.post(
    "/cohorts/{cohort_id}/students/{student_id}/lessons/{lesson_id}/messages",
    response_model=AgentResponse,
)
async def send_student_message(
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_id: uuid.UUID,
    body: MessageIn,
    user: Annotated[User, Depends(admin_only)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Envia mensagem como aluno matriculado — sessão segregada por turma e aluno."""
    await _get_cohort_or_404(db, cohort_id)
    await _ensure_enrolled_student(db, cohort_id, student_id)
    return await student_lesson_message(db, cohort_id, lesson_id, student_id, body.content)


@router.post(
    "/cohorts/{cohort_id}/professors/{professor_id}/transcribe-report",
    response_model=TranscriptionOut,
)
async def transcribe_lesson_report(
    cohort_id: uuid.UUID,
    professor_id: uuid.UUID,
    lesson_id: Annotated[uuid.UUID, Query(description="Aula do relato")],
    user: Annotated[User, Depends(admin_only)],
    db: Annotated[AsyncSession, Depends(get_db)],
    audio: Annotated[UploadFile, File(description="Áudio do relato da aula")],
):
    """Transcreve relato como professor do módulo — somente admin."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _ensure_module_professor(db, cohort_id, professor_id, lesson_id)

    if not audio.content_type or not (
        audio.content_type.startswith("audio/") or audio.content_type == "video/webm"
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo deve ser de áudio")

    content = await audio.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Áudio vazio")
    if len(content) > 25 * 1024 * 1024:
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


@router.post("/cohorts/{cohort_id}/professors/{professor_id}/complete-lesson")
async def complete_lesson_as_professor(
    cohort_id: uuid.UUID,
    professor_id: uuid.UUID,
    body: LessonCompletionIn,
    user: Annotated[User, Depends(admin_only)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Encerra aula como professor do módulo — somente admin."""
    cohort = await _get_cohort_or_404(db, cohort_id)
    await _ensure_module_professor(db, cohort_id, professor_id, body.lesson_id)

    current = await _current_lesson_id(db, cohort)
    if current is not None and body.lesson_id != current:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Só é possível encerrar a aula atual da turma",
        )

    try:
        note = await complete_lesson(db, cohort_id, body.lesson_id, body.transcript)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

    return {
        "status": "aula encerrada, turma avançada",
        "summary": note.summary,
        "unclear_points": note.unclear_points,
    }
