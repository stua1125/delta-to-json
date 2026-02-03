"""
Authentication module - OAuth and JWT handling.
"""

from app.auth.jwt import create_access_token, get_current_user, get_optional_user
from app.auth.oauth import oauth
from app.auth.router import router

__all__ = [
    "router",
    "oauth",
    "create_access_token",
    "get_current_user",
    "get_optional_user",
]
