"""Repository for the analysis_events table."""

from typing import Optional
from app.database.repositories.base import BaseRepository


class AnalysisEventRepository(BaseRepository):
    """Repository for analysis_events table."""

    def __init__(self, client):
        super().__init__(client, "analysis_events")

    async def get_by_analysis_id(self, analysis_id: str) -> list:
        """Fetch all events for an analysis."""
        result = self._table.select("*").eq("analysis_id", analysis_id).order("timestamp").execute()
        return result.data or []

    async def insert_batch(self, events: list) -> list:
        """Insert multiple analysis events."""
        result = self._table.insert(events).execute()
        return result.data or []