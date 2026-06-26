from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.schemas import RefreshRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await db.scalar(select(User).where(User.email == form.username))
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conta inativa")

    sub, role = str(user.id), user.role.value
    return Token(
        access_token=create_access_token(sub, role),
        refresh_token=create_refresh_token(sub, role),
    )


@router.post("/refresh", response_model=Token)
async def refresh(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada. Entre novamente."
        )
    sub, role = payload["sub"], payload["role"]
    return Token(
        access_token=create_access_token(sub, role),
        refresh_token=create_refresh_token(sub, role),
    )
