"""
History service for parse history CRUD operations.
"""

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParseHistory, User
from app.schemas import ParseHistoryCreate, ParseHistoryListItem


class HistoryService:
    """Service for managing parse history."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user: User,
        data: ParseHistoryCreate,
    ) -> ParseHistory:
        """Create a new parse history record."""
        history = ParseHistory(
            user_id=user.id,
            format_type=data.format_type,
            input_logs=data.input_logs,
            raw_text=data.raw_text,
            json_data=data.json_data,
            usage_data=data.usage_data,
            metadata_info=data.metadata_info,
            chunk_count=data.chunk_count,
        )
        self.db.add(history)
        await self.db.flush()
        return history

    async def get_by_id(
        self,
        history_id: uuid.UUID,
        user: User,
    ) -> ParseHistory | None:
        """Get a parse history record by ID for the given user."""
        result = await self.db.execute(
            select(ParseHistory).where(
                ParseHistory.id == history_id,
                ParseHistory.user_id == user.id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ParseHistoryListItem], int]:
        """List parse history for a user with pagination."""
        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(ParseHistory).where(
                ParseHistory.user_id == user.id
            )
        )
        total = count_result.scalar() or 0

        # Get items
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(ParseHistory)
            .where(ParseHistory.user_id == user.id)
            .order_by(ParseHistory.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        histories = result.scalars().all()

        # Convert to list items with preview
        items = []
        for h in histories:
            preview = None
            if h.raw_text:
                preview = h.raw_text[:100] + ("..." if len(h.raw_text) > 100 else "")
            items.append(
                ParseHistoryListItem(
                    id=h.id,
                    format_type=h.format_type,
                    chunk_count=h.chunk_count,
                    created_at=h.created_at,
                    preview=preview,
                )
            )

        return items, total

    async def delete(
        self,
        history_id: uuid.UUID,
        user: User,
    ) -> bool:
        """Delete a parse history record."""
        result = await self.db.execute(
            delete(ParseHistory).where(
                ParseHistory.id == history_id,
                ParseHistory.user_id == user.id,
            )
        )
        return result.rowcount > 0

    async def delete_all_for_user(self, user: User) -> int:
        """Delete all parse history for a user."""
        result = await self.db.execute(
            delete(ParseHistory).where(ParseHistory.user_id == user.id)
        )
        return result.rowcount
