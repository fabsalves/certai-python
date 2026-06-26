import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.cohort import Enrollment
from app.models.user import Role, User
from app.schemas import AgentResponse, MessageIn
from app.services.conversation_service import student_lesson_message

router = APIRouter(prefix="/conversations", tags=["conversations"])

student_only = require_roles(Role.STUDENT)


async def _ensure_enrolled(db: AsyncSession, cohort_id: uuid.UUID, student_id: uuid.UUID):
    e = await db.scalar(
        select(Enrollment).where(
            Enrollment.cohort_id == cohort_id, Enrollment.student_id == student_id
        )
    )
    if e is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não está matriculado nesta turma")


@router.post("/cohorts/{cohort_id}/lessons/{lesson_id}/messages", response_model=AgentResponse)
async def converse(
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    body: MessageIn,
    user: Annotated[User, Depends(student_only)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Student talks to Lira within a lesson scope. Segregated per cohort."""
    await _ensure_enrolled(db, cohort_id, user.id)
    return await student_lesson_message(db, cohort_id, lesson_id, user.id, body.content)
