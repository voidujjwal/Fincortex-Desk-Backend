"""Repository for the watchlist table."""

from typing import Optional, List
from app.database.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository):
    """Repository for watchlist table."""

    def __init__(self, client):
        super().__init__(client, "watchlist")

    async def get_by_user_id(self, user_id: str) -> List[dict]:
        """Fetch all watchlist items for a user."""
        result = self._table.select("*").eq("user_id", user_id).execute()
        return result.data or []

    async def add_item(self, user_id: str, ticker: str) -> dict:
        """Add a ticker to the user's watchlist."""
        return self.insert({"user_id": user_id, "ticker": ticker})

    async def remove_item(self, item_id: str) -> bool:
        """Remove a watchlist item by id."""
        return self.delete(item_id)