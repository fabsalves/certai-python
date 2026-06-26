from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.core.security import hash_password
from app.models.user import Role, User
from app.schemas import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])

can_manage_users = require_roles(Role.ADMIN, Role.DESIGNER)

_DESIGNER_CREATABLE = {Role.STUDENT, Role.PROFESSOR}


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
    if user.role == Role.DESIGNER:
        if body.role not in _DESIGNER_CREATABLE:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Designer só pode cadastrar alunos e professores",
            )
    elif user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não tem permissão para esta ação")

    if await db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado"
        )
    new_user = User(
        email=body.email,
        name=body.name,
        role=body.role,
        hashed_password=hash_password(body.password),
    )
    db.add(new_user)
    await db.flush()
    return new_user
