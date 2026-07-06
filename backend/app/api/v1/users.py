from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.core.security import hash_password
from app.models.user import Role, User
from app.schemas import (
    StudentBulkCreate,
    StudentBulkOut,
    StudentBulkSkipped,
    UserCreate,
    UserOut,
)

router = APIRouter(prefix="/users", tags=["users"])

can_manage_users = require_roles(Role.ADMIN, Role.DESIGNER)

_DESIGNER_CREATABLE = {Role.STUDENT, Role.PROFESSOR}


def _assert_can_create(user: User, role: Role) -> None:
    if user.role == Role.DESIGNER:
        if role not in _DESIGNER_CREATABLE:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Designer só pode cadastrar alunos e professores",
            )
    elif user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não tem permissão para esta ação")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.get(
    "",
    response_model=list[UserOut],
    dependencies=[Depends(can_manage_users)],
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    role: Role | None = Query(None),
):
    stmt = select(User).where(User.is_active.is_(True))
    if role is not None:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.name)
    return (await db.execute(stmt)).scalars().all()


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    body: UserCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _assert_can_create(user, body.role)

    if await db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado"
        )
    if body.whatsapp and await db.scalar(select(User).where(User.whatsapp == body.whatsapp)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="WhatsApp já cadastrado"
        )
    new_user = User(
        email=body.email,
        name=body.name,
        role=body.role,
        hashed_password=hash_password(body.password),
        whatsapp=body.whatsapp,
    )
    db.add(new_user)
    await db.flush()
    return new_user


@router.post(
    "/bulk",
    response_model=StudentBulkOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_students_bulk(
    body: StudentBulkCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _assert_can_create(user, Role.STUDENT)

    unique_students: list = []
    seen_emails: set[str] = set()
    for item in body.students:
        if item.email in seen_emails:
            continue
        seen_emails.add(item.email)
        unique_students.append(item)

    if not unique_students:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe ao menos um aluno")

    emails = [item.email for item in unique_students]
    whatsapps = [item.whatsapp for item in unique_students]

    existing_by_email = {
        row.email: row
        for row in (await db.execute(select(User).where(User.email.in_(emails)))).scalars().all()
    }
    existing_by_whatsapp = {
        row.whatsapp: row
        for row in (
            await db.execute(select(User).where(User.whatsapp.in_(whatsapps)))
        ).scalars().all()
        if row.whatsapp
    }

    created: list[User] = []
    reused_ids: list = []
    skipped: list[StudentBulkSkipped] = []
    whatsapps_in_batch: set[str] = set()

    for item in unique_students:
        if item.whatsapp in whatsapps_in_batch:
            skipped.append(
                StudentBulkSkipped(email=item.email, reason="WhatsApp duplicado no lote")
            )
            continue
        whatsapps_in_batch.add(item.whatsapp)

        existing = existing_by_email.get(item.email)
        if existing is not None:
            if existing.role == Role.STUDENT and existing.is_active:
                reused_ids.append(existing.id)
            else:
                skipped.append(
                    StudentBulkSkipped(email=item.email, reason="E-mail já cadastrado")
                )
            continue

        wa_owner = existing_by_whatsapp.get(item.whatsapp)
        if wa_owner is not None:
            skipped.append(
                StudentBulkSkipped(email=item.email, reason="WhatsApp já cadastrado")
            )
            continue

        new_user = User(
            email=item.email,
            name=item.name,
            role=Role.STUDENT,
            hashed_password=hash_password(body.password),
            whatsapp=item.whatsapp,
        )
        db.add(new_user)
        await db.flush()
        created.append(new_user)
        existing_by_email[item.email] = new_user
        existing_by_whatsapp[item.whatsapp] = new_user

    return StudentBulkOut(created=created, reused_ids=reused_ids, skipped=skipped)
