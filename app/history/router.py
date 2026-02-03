"""
History API routes.
"""

import uuid
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.database import get_db
from app.history.service import HistoryService
from app.models import User
from app.schemas import PaginatedResponse, ParseHistoryListItem, ParseHistoryResponse

router = APIRouter(prefix="/history", tags=["history"])


def get_history_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HistoryService:
    """Get history service instance."""
    return HistoryService(db)


@router.get("", response_model=PaginatedResponse)
async def list_history(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[HistoryService, Depends(get_history_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """List user's parse history with pagination."""
    items, total = await service.list_for_user(current_user, page, page_size)
    total_pages = ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=[item.model_dump() for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{history_id}", response_model=ParseHistoryResponse)
async def get_history(
    history_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[HistoryService, Depends(get_history_service)],
):
    """Get a specific parse history record."""
    history = await service.get_by_id(history_id, current_user)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History not found",
        )
    return history


@router.delete("/{history_id}")
async def delete_history(
    history_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[HistoryService, Depends(get_history_service)],
):
    """Delete a parse history record."""
    deleted = await service.delete(history_id, current_user)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History not found",
        )
    return {"message": "Deleted"}


@router.delete("")
async def delete_all_history(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[HistoryService, Depends(get_history_service)],
):
    """Delete all parse history for the current user."""
    count = await service.delete_all_for_user(current_user)
    return {"message": f"Deleted {count} records"}
