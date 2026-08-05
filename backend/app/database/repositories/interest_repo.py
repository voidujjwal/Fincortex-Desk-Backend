"""Repository for the user_interests table."""

from typing import List, Optional

from app.database.repositories.base import BaseRepository


class InterestRepository(BaseRepository):
    """Repository for user_interests table."""

    def __init__(self, client):
        super().__init__(client, "user_interests")

    async def get_by_user_id(self, user_id: str) -> List[dict]:
        """Fetch all interests for a user, most recent first."""
        result = (
            self._table.select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    async def get_by_user_and_ticker(self, user_id: str, ticker: str) -> Optional[dict]:
        """Fetch a single interest row for a user + ticker."""
        result = (
            self._table.select("*")
            .eq("user_id", user_id)
            .eq("ticker", ticker)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]
        return None

    async def upsert(self, user_id: str, ticker: str, market: str, source: str) -> Optional[dict]:
        """Insert a user interest, or update market/source if it already exists.

        Uses on_conflict on the (user_id, ticker) unique constraint so adding
        a researched stock that is already watched does not create a duplicate.
        """
        result = (
            self._table.insert({
                "user_id": user_id,
                "ticker": ticker.upper(),
                "market": market,
                "source": source,
            })
            .on_conflict("user_id,ticker")
            .update({"market": market, "source": source})
            .execute()
        )
        if result.data:
            return result.data[0]
        return None

    async def remove_by_ticker(self, user_id: str, ticker: str) -> bool:
        """Remove a user's interest in a ticker."""
        self._table.delete().eq("user_id", user_id).eq("ticker", ticker.upper()).execute()
        return True

    async def sync(self, user_id: str, items: List[dict]) -> int:
        """Bulk upsert interests (first-load seed).

        On conflict the row is left untouched (seed must not overwrite
        existing research/watchlist sources).

        Args:
            items: list of {"ticker": str, "market": str, "source": str}
        Returns:
            Number of rows synced.
        """
        if not items:
            return 0
        rows = [
            {
                "user_id": user_id,
                "ticker": item["ticker"].upper(),
                "market": item.get("market", "US"),
                "source": item.get("source", "watchlist"),
            }
            for item in items
            if item.get("ticker")
        ]
        if not rows:
            return 0
        result = (
            self._table.upsert(rows, on_conflict="user_id,ticker", ignore_duplicates=True)
            .execute()
        )
        return len(result.data or []) if result.data else 0

    async def all_interests(self) -> List[dict]:
        """Fetch every interest row across all users (scheduler usage)."""
        result = self._table.select("user_id, ticker, market").execute()
        return result.data or []
