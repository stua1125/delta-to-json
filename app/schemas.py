"""
Pydantic schemas for API request/response models.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# User schemas
class UserBase(BaseModel):
    """Base user schema."""
    email: str
    name: str | None = None
    picture: str | None = None


class UserResponse(UserBase):
    """User response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    created_at: datetime
    last_login_at: datetime | None = None


class UserInToken(BaseModel):
    """User info stored in JWT token."""
    sub: str  # user_id as string
    email: str
    name: str | None = None


# Parse history schemas
class ParseHistoryBase(BaseModel):
    """Base parse history schema."""
    format_type: str
    input_logs: str
    raw_text: str | None = None
    json_data: dict | None = None
    usage_data: dict | None = None
    metadata_info: dict | None = None
    chunk_count: int = 0


class ParseHistoryCreate(ParseHistoryBase):
    """Schema for creating parse history."""
    pass


class ParseHistoryResponse(ParseHistoryBase):
    """Parse history response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime


class ParseHistoryListItem(BaseModel):
    """Simplified parse history for list display."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    format_type: str
    chunk_count: int
    created_at: datetime
    # Preview of raw_text (first 100 chars)
    preview: str | None = None


class PaginatedResponse(BaseModel):
    """Generic paginated response."""
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
