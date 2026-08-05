"""Repository for the analyses table."""

from typing import Optional
from app.database.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository):
    """Repository for analyses table."""

    def __init__(self, client):
        super().__init__(client, "analyses")

    async def get_by_job_id(self, job_id: str) -> Optional[dict]:
        """Fetch an analysis by its id."""
        result = self._table.select("*").eq("id", job_id).execute()
        if result.data:
            return result.data[0]
        return None

    async def list_by_user(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> list:
        """Fetch paginated analyses for a user."""
        offset = (page - 1) * page_size
        result = (
            self._table.select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        return result.data or []

    async def count_by_user(self, user_id: str) -> int:
        """Count total analyses for a user."""
        result = self._table.select("id", count="exact").eq("user_id", user_id).execute()
        return result.count or 0