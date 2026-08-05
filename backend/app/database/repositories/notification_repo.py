"""Repository for the notifications table."""

from typing import Optional, List
from app.database.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    """Repository for notifications table."""

    def __init__(self, client):
        super().__init__(client, "notifications")

    async def get_by_user_id(self, user_id: str, limit: int = 50) -> List[dict]:
        """Fetch notifications for a user."""
        result = (
            self._table.select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    async def create(self, user_id: str, title: str, message: str) -> dict:
        """Create a new notification."""
        return self.insert({"user_id": user_id, "title": title, "message": message})