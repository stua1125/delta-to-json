"""
JWT token creation and validation.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import UserInToken

settings = get_settings()

TOKEN_COOKIE_NAME = "access_token"


def create_access_token(user: User) -> str:
    """Create JWT access token for user."""
    expire = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> UserInToken | None:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return UserInToken(
            sub=payload["sub"],
            email=payload["email"],
            name=payload.get("name"),
        )
    except JWTError:
        return None


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    """Get current authenticated user from JWT cookie."""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token_data = decode_token(access_token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id = uuid.UUID(token_data.sub)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_optional_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> User | None:
    """Get current user if authenticated, otherwise None."""
    if not access_token:
        return None

    token_data = decode_token(access_token)
    if not token_data:
        return None

    try:
        user_id = uuid.UUID(token_data.sub)
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except (ValueError, Exception):
        return None
