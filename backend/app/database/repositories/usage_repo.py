"""Repository for the usage table."""

from typing import Optional
from datetime import date
from app.database.repositories.base import BaseRepository


class UsageRepository(BaseRepository):
    """Repository for usage table."""

    def __init__(self, client):
        super().__init__(client, "usage")

    async def get_today_usage(self, user_id: str) -> int:
        """Get the number of analyses used today by a user."""
        today = date.today().isoformat()
        result = (
            self._table.select("analysis_count")
            .eq("user_id", user_id)
            .eq("date", today)
            .execute()
        )
        if result.data:
            return result.data[0].get("analysis_count", 0)
        return 0

    async def record_usage(self, user_id: str, analysis_id: str) -> dict:
        """Record a new usage entry for today."""
        today = date.today().isoformat()
        existing = (
            self._table.select("*")
            .eq("user_id", user_id)
            .eq("date", today)
            .execute()
        )
        if existing.data:
            new_count = existing.data[0].get("analysis_count", 0) + 1
            result = (
                self._table.update({"analysis_count": new_count})
                .eq("user_id", user_id)
                .eq("date", today)
                .execute()
            )
            return result.data[0]
        else:
            data = {
                "user_id": user_id,
                "date": today,
                "analysis_count": 1,
            }
            result = self._table.insert(data).execute()
            return result.data[0]