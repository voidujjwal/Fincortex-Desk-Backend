"""Repository for the news_cache table."""

from typing import Optional

from app.database.repositories.base import BaseRepository


class NewsCacheRepository(BaseRepository):
    """Repository for the shared per-ticker news_cache table."""

    def __init__(self, client):
        super().__init__(client, "news_cache")

    async def get_by_ticker(self, ticker: str) -> Optional[dict]:
        """Fetch the cached news row for a ticker."""
        result = self._table.select("*").eq("ticker", ticker).limit(1).execute()
        if result.data:
            return result.data[0]
        return None

    async def upsert(self, ticker: str, news: list, fetched_at: Optional[str] = None) -> Optional[dict]:
        """Insert or replace the cached news for a ticker."""
        data = {
            "ticker": ticker.upper(),
            "news": news,
        }
        if fetched_at:
            data["fetched_at"] = fetched_at
        result = (
            self._table.upsert(data, on_conflict="ticker")
            .execute()
        )
        if result.data:
            return result.data[0]
        return None
