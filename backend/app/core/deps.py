import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
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
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[..., Coroutine[Any, Any, User]]:
    """Guarda de rota: só passa se o usuário tiver um dos papéis informados.

    Uso: dependencies=[Depends(require_roles(Role.DESIGNER, Role.ADMIN))]
    ou injetando: user = Depends(require_roles(Role.PROFESSOR))
    """

    async def _guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para esta ação",
            )
        return user

    return _guard
