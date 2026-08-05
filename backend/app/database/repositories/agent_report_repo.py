"""Repository for the agent_reports table."""

from typing import Optional
from app.database.repositories.base import BaseRepository


class AgentReportRepository(BaseRepository):
    """Repository for agent_reports table."""

    def __init__(self, client):
        super().__init__(client, "agent_reports")

    async def get_by_analysis_id(self, analysis_id: str) -> list:
        """Fetch all agent reports for an analysis."""
        result = self._table.select("*").eq("analysis_id", analysis_id).execute()
        return result.data or []

    async def insert_batch(self, reports: list) -> list:
        """Insert multiple agent reports."""
        result = self._table.insert(reports).execute()
        return result.data or []