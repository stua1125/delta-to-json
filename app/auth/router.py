"""
Authentication routes for OAuth login/logout.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import TOKEN_COOKIE_NAME, create_access_token, get_current_user
from app.auth.oauth import oauth
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.get("/google")
async def login_google(request: Request):
    """Initiate Google OAuth login."""
    if not settings.google_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth not configured",
        )
    redirect_uri = f"{settings.app_url}/auth/callback/google"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/github")
async def login_github(request: Request):
    """Initiate GitHub OAuth login."""
    if not settings.github_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth not configured",
        )
    redirect_uri = f"{settings.app_url}/auth/callback/github"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/callback/google")
async def callback_google(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Handle Google OAuth callback."""
    if not settings.google_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth not configured",
        )

    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info from Google",
            )

        return await _handle_oauth_user(
            db=db,
            provider="google",
            provider_id=user_info["sub"],
            email=user_info["email"],
            name=user_info.get("name"),
            picture=user_info.get("picture"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {str(e)}",
        )


@router.get("/callback/github")
async def callback_github(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Handle GitHub OAuth callback."""
    if not settings.github_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth not configured",
        )

    try:
        token = await oauth.github.authorize_access_token(request)
        resp = await oauth.github.get("user", token=token)
        user_data = resp.json()

        # Get primary email if not public
        email = user_data.get("email")
        if not email:
            emails_resp = await oauth.github.get("user/emails", token=token)
            emails = emails_resp.json()
            primary_email = next(
                (e for e in emails if e.get("primary") and e.get("verified")),
                None,
            )
            if primary_email:
                email = primary_email["email"]

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not get email from GitHub",
            )

        return await _handle_oauth_user(
            db=db,
            provider="github",
            provider_id=str(user_data["id"]),
            email=email,
            name=user_data.get("name") or user_data.get("login"),
            picture=user_data.get("avatar_url"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {str(e)}",
        )


async def _handle_oauth_user(
    db: AsyncSession,
    provider: str,
    provider_id: str,
    email: str,
    name: str | None,
    picture: str | None,
) -> RedirectResponse:
    """Handle OAuth user login/registration."""
    # Check if user exists by provider
    result = await db.execute(
        select(User).where(
            User.provider == provider,
            User.provider_id == provider_id,
        )
    )
    user = result.scalar_one_or_none()

    if user:
        # Update existing user
        user.email = email
        user.name = name
        user.picture = picture
        user.last_login_at = datetime.now(UTC)
    else:
        # Check if email exists with different provider
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            # Link to existing account by updating provider info
            existing.provider = provider
            existing.provider_id = provider_id
            existing.name = name
            existing.picture = picture
            existing.last_login_at = datetime.now(UTC)
            user = existing
        else:
            # Create new user
            user = User(
                email=email,
                name=name,
                picture=picture,
                provider=provider,
                provider_id=provider_id,
                last_login_at=datetime.now(UTC),
            )
            db.add(user)

    await db.flush()

    # Create JWT token
    access_token = create_access_token(user)

    # Redirect to home with cookie
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        max_age=settings.jwt_expire_hours * 3600,
        samesite="lax",
    )
    return response


@router.post("/logout")
async def logout():
    """Log out current user by clearing cookie."""
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie(key=TOKEN_COOKIE_NAME)
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get current authenticated user info."""
    return current_user


@router.get("/status")
async def auth_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: str | None = None,
):
    """Check authentication status and available providers."""
    from app.auth.jwt import get_optional_user

    user = await get_optional_user(db, access_token)

    return {
        "authenticated": user is not None,
        "user": UserResponse.model_validate(user) if user else None,
        "providers": {
            "google": settings.google_enabled,
            "github": settings.github_enabled,
        },
    }
