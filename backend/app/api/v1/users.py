from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_org_scope, require_roles
from app.core.passwords import validate_new_password
from app.core.security import generate_password, hash_password
from app.models.user import Role, User
from app.schemas import (
    PasswordUpdate,
    StudentBulkCreate,
    StudentBulkOut,
    StudentBulkSkipped,
    UserCreate,
    UserCreatedOut,
    UserOut,
    UserUpdate,
)
from app.services.access import (
    assert_assignable_role,
    assert_same_org,
    validate_user_update,
)

router = APIRouter(prefix="/users", tags=["users"])

can_manage_users = require_roles(Role.ORG_ADMIN)


def _assert_can_create(user: User, role: Role) -> None:
    if user.role != Role.ORG_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não tem permissão para esta ação")
    assert_assignable_role(role)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.get(
    "",
    response_model=list[UserOut],
    dependencies=[Depends(can_manage_users)],
)
async def list_users(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    role: Role | None = Query(None),
):
    org_id = require_org_scope(user)
    stmt = select(User).where(
        User.organization_id == org_id,
        User.role != Role.SUPERADMIN,
    )
    if role is not None:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.name)
    return (await db.execute(stmt)).scalars().all()


@router.post(
    "",
    response_model=UserCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    body: UserCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _assert_can_create(user, body.role)
    org_id = require_org_scope(user)

    if await db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado"
        )
    if body.whatsapp and await db.scalar(select(User).where(User.whatsapp == body.whatsapp)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="WhatsApp já cadastrado"
        )
    plain = generate_password()
    new_user = User(
        organization_id=org_id,
        email=body.email,
        name=body.name,
        role=body.role,
        hashed_password=hash_password(plain),
        whatsapp=body.whatsapp,
    )
    db.add(new_user)
    await db.flush()
    created = UserCreatedOut.model_validate(new_user)
    if body.role != Role.STUDENT:
        return created.model_copy(update={"initial_password": plain})
    return created


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
    org_id = require_org_scope(user)

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
            if (
                existing.role == Role.STUDENT
                and existing.is_active
                and existing.organization_id == org_id
            ):
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
            organization_id=org_id,
            email=item.email,
            name=item.name,
            role=Role.STUDENT,
            hashed_password=hash_password(generate_password()),
            whatsapp=item.whatsapp,
        )
        db.add(new_user)
        await db.flush()
        created.append(new_user)
        existing_by_email[item.email] = new_user
        existing_by_whatsapp[item.whatsapp] = new_user

    return StudentBulkOut(created=created, reused_ids=reused_ids, skipped=skipped)


@router.patch(
    "/{user_id}",
    response_model=UserOut,
)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    actor: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    if target.role == Role.SUPERADMIN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este usuário não pode ser editado")

    if actor.id == target.id:
        if target.role == Role.STUDENT and not body.whatsapp:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "WhatsApp é obrigatório para alunos",
            )
        if body.role is not None or body.is_active is not None:
            validate_user_update(actor, target, role=body.role, is_active=body.is_active)
    elif actor.role == Role.ORG_ADMIN:
        assert_same_org(actor, target.organization_id)
        if target.role == Role.STUDENT and body.whatsapp is None and not target.whatsapp:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "WhatsApp é obrigatório para alunos",
            )
        validate_user_update(actor, target, role=body.role, is_active=body.is_active)
    else:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você não tem permissão para esta ação",
        )

    if body.email != target.email:
        if await db.scalar(select(User).where(User.email == body.email)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="E-mail já cadastrado",
            )

    if target.role == Role.STUDENT and body.whatsapp and body.whatsapp != target.whatsapp:
        if await db.scalar(select(User).where(User.whatsapp == body.whatsapp)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="WhatsApp já cadastrado",
            )

    target.name = body.name
    target.email = body.email
    if target.role == Role.STUDENT and body.whatsapp is not None:
        target.whatsapp = body.whatsapp
    if actor.role == Role.ORG_ADMIN and actor.id != target.id:
        if body.role is not None:
            target.role = body.role
        if body.is_active is not None:
            target.is_active = body.is_active
    await db.flush()
    return target


@router.patch("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_user_password(
    user_id: UUID,
    body: PasswordUpdate,
    actor: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        validate_new_password(body.password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    target = await db.get(User, user_id)
    if target is None or target.role == Role.SUPERADMIN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")

    if actor.role == Role.ORG_ADMIN:
        assert_same_org(actor, target.organization_id)
    elif actor.id != target.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não tem permissão para esta ação")

    target.hashed_password = hash_password(body.password)
    target.token_version = int(target.token_version or 0) + 1
    await db.flush()
