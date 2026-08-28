from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.email import normalize_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    token_version_matches,
    verify_password,
)
from app.models.user import User
from app.schemas import RefreshRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(user: User) -> Token:
    org = str(user.organization_id) if user.organization_id else ""
    return Token(
        access_token=create_access_token(
            str(user.id), user.role.value, org=org, token_version=user.token_version
        ),
        refresh_token=create_refresh_token(
            str(user.id), user.role.value, org=org, token_version=user.token_version
        ),
    )


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    email = normalize_email(form.username)
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conta inativa")
    return _token_pair(user)


@router.post("/refresh", response_model=Token)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada. Entre novamente."
        )
    user = await db.get(User, user_id)
    if user is None or not user.is_active or not token_version_matches(payload, user.token_version):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada. Entre novamente."
        )
    return _token_pair(user)
