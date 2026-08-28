import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, token_version_matches
from app.models.user import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Não foi possível validar as credenciais",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        payload = decode_token(token, expected_type="access")
        user_id = payload.get("sub")
        if user_id is None:
            raise CREDENTIALS_EXC
    except jwt.InvalidTokenError:
        raise CREDENTIALS_EXC

    user = await db.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise CREDENTIALS_EXC
    if not token_version_matches(payload, user.token_version):
        raise CREDENTIALS_EXC
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[..., Coroutine[Any, Any, User]]:
    """Guarda de rota: só passa se o usuário tiver um dos papéis informados."""

    async def _guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para esta ação",
            )
        return user

    return _guard


require_org_admin = require_roles(Role.ORG_ADMIN)
require_superadmin = require_roles(Role.SUPERADMIN)


async def require_org_user(user: CurrentUser) -> User:
    """Org-bound users only — superadmin has no product access without a selected org."""
    if user.role == Role.SUPERADMIN or user.organization_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    return user


def require_org_scope(user: User) -> uuid.UUID:
    if user.organization_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário sem organização.")
    return user.organization_id


def org_id_for_product(
    user: User,
    selected_org_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Org for product screens. Superadmin must pass a selected org; others use their own."""
    if user.role == Role.SUPERADMIN:
        if selected_org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selecione uma organização.",
            )
        return selected_org_id
    return require_org_scope(user)


OrgIdQuery = Annotated[uuid.UUID | None, Query(alias="org_id")]
