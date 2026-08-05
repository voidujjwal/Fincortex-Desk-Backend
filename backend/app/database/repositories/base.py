"""Base repository class for Supabase table operations."""

from typing import Optional, List, Dict, Any
from supabase import Client


class BaseRepository:
    """Base repository providing common Supabase operations."""

    def __init__(self, client: Client, table_name: str):
        self._client = client
        self._table = client.table(table_name)
        self._table_name = table_name

    async def get_by_id(self, record_id: str) -> Optional[dict]:
        """Fetch a single record by its id."""
        result = self._table.select("*").eq("id", record_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    async def insert(self, data: dict) -> dict:
        """Insert a new record and return it."""
        result = self._table.insert(data).execute()
        if result.data:
            return result.data[0]
        raise RuntimeError(f"Insert failed for {self._table_name}")

    async def update(self, record_id: str, data: dict) -> Optional[dict]:
        """Update a record by id and return the updated record."""
        result = self._table.update(data).eq("id", record_id).execute()
        if result.data:
            return result.data[0]
        return None

    async def delete(self, record_id: str) -> bool:
        """Delete a record by id."""
        result = self._table.delete().eq("id", record_id).execute()
        return True

    async def list_all(self) -> List[dict]:
        """Fetch all records from the table."""
        result = self._table.select("*").execute()
        return result.data or []

    async def list_by_column(
        self, column: str, value: Any, limit: int = 100
    ) -> List[dict]:
        """Fetch records filtered by a column value."""
        result = (
            self._table.select("*").eq(column, value).limit(limit).execute()
        )
        return result.data or []