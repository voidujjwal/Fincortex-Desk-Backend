"""Repository for the settings table."""

from typing import Optional
from app.database.repositories.base import BaseRepository


class SettingsRepository(BaseRepository):
    """Repository for settings table."""

    def __init__(self, client):
        super().__init__(client, "settings")

    async def get_by_user_id(self, user_id: str) -> Optional[dict]:
        """Fetch settings for a user."""
        result = self._table.select("*").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0]
        return None

    async def upsert(self, user_id: str, data: dict) -> dict:
        """Upsert settings for a user."""
        existing = await self.get_by_user_id(user_id)
        if existing:
            return await self.update(existing["id"], data)
        data["user_id"] = user_id
        return await self.insert(data)