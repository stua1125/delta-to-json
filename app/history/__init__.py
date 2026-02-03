"""
History module - Parse history CRUD operations.
"""

from app.history.router import router
from app.history.service import HistoryService

__all__ = ["router", "HistoryService"]
