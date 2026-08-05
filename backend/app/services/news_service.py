"""News service — fetches yfinance news for user interests and caches it.

Responsibilities:
- Fetch structured news (headline/summary/source/url/published_at) per ticker
  from yfinance (reusing the tradingagents extraction helper).
- Cache results in the shared news_cache table (one row per ticker).
- Serve a user's personalized feed by joining their user_interests with the
  cache, refreshing stale entries on demand.
- Run a background scheduler that refreshes all interests every
  NEWS_REFRESH_INTERVAL_HOURS (default 4).
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config.settings import Settings, get_settings
from app.database import get_supabase_client
from app.database.repositories.interest_repo import InterestRepository
from app.database.repositories.news_cache_repo import NewsCacheRepository
from app.utils.helpers import utc_now

logger = logging.getLogger("tradingagents.news")

# Max articles kept per ticker (matches the old client-side feed size).
NEWS_PER_TICKER = 9

_BULLISH_WORDS = (
    "beat", "beats", "surge", "surges", "surged", "raise", "raises", "raised",
    "buyback", "record", "wins", "rally", "rallies", "soar", "soars", "soared",
    "upgrade", "upgraded", "bullish", "growth", "gains", "jump", "jumps",
    "jumped", "high", "higher", "strong", "profit", "profitable", "outperform",
    "dividend", "expansion", "partnership",
)

_BEARISH_WORDS = (
    "miss", "misses", "cut", "cuts", "downgrade", "downgraded", "probe",
    "warning", "warns", "fall", "falls", "fell", "drop", "drops", "dropped",
    "decline", "declines", "sell", "selling", "short interest", "loss",
    "loses", "losing", "pressure", "plunge", "plunges", "lawsuit",
    "regulatory", "lower", "weak", "weakness", "layoff", "layoffs", "fraud",
    "investigation", "bearish", "underperform", "scrutiny",
)


def _keyword_sentiment(text: str) -> str:
    """Simple keyword-based sentiment: Bullish | Bearish | Neutral."""
    if not text:
        return "Neutral"
    lower = text.lower()
    bullish_hits = sum(1 for w in _BULLISH_WORDS if w in lower)
    bearish_hits = sum(1 for w in _BEARISH_WORDS if w in lower)
    if bullish_hits > bearish_hits:
        return "Bullish"
    if bearish_hits > bullish_hits:
        return "Bearish"
    return "Neutral"


def _normalize_ticker(ticker: str, market: str) -> str:
    """Map display tickers to yfinance symbols."""
    t = (ticker or "").strip().upper()
    if market and market.lower() == "crypto":
        if "." not in t and "-" not in t:
            return f"{t}-USD"
    return t


class NewsService:
    """Coordinates interest tracking, news fetching, caching, and scheduling."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.supabase = get_supabase_client(self.settings)
        self.interest_repo = InterestRepository(self.supabase)
        self.cache_repo = NewsCacheRepository(self.supabase)

    # ------------------------------------------------------------------
    # yfinance fetching (sync, runs in a worker thread)
    # ------------------------------------------------------------------

    def _fetch_ticker_news_sync(self, ticker: str, market: str) -> list:
        """Fetch + structure news for one ticker (blocking; run in a thread)."""
        symbol = _normalize_ticker(ticker, market)
        try:
            from tradingagents.dataflows.yfinance_news import _extract_article_data

            import yfinance as yf

            stock = yf.Ticker(symbol)
            raw = stock.get_news(count=20) or []

            company = ticker.upper()
            try:
                info = stock.info or {}
                company = info.get("shortName") or info.get("longName") or company
            except Exception:
                pass

            items = []
            for article in raw[:NEWS_PER_TICKER]:
                data = _extract_article_data(article)
                if not data.get("title"):
                    continue
                published_at = data.get("pub_date")
                time_str = (
                    published_at.isoformat()
                    if isinstance(published_at, datetime)
                    else (published_at or "").isoformat() if hasattr(published_at, "isoformat") else str(published_at or "")
                )
                headline = data.get("title", "")
                summary = data.get("summary", "")
                text = f"{headline} {summary}"
                items.append({
                    "headline": headline,
                    "summary": summary,
                    "source": data.get("publisher") or "Unknown",
                    "url": data.get("link") or "",
                    "published_at": time_str,
                    "sentiment": _keyword_sentiment(text),
                    "impact": "Medium",
                    "company": company,
                })
            if not items:
                logger.info("[news] No articles returned for %s (%s)", ticker, symbol)
            return items
        except Exception as exc:
            logger.warning("[news] Failed to fetch news for %s: %s", ticker, exc)
            return []

    async def fetch_ticker_news(self, ticker: str, market: str) -> list:
        """Fetch structured news for one ticker (async wrapper)."""
        return await asyncio.to_thread(self._fetch_ticker_news_sync, ticker, market)

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _is_stale(self, row: Optional[dict]) -> bool:
        """A cache row is stale when missing, empty, or older than the interval."""
        if not row:
            return True
        fetched_raw = row.get("fetched_at")
        if not fetched_raw:
            return True
        try:
            fetched = datetime.fromisoformat(str(fetched_raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return True
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return utc_now() - fetched > timedelta(hours=self.settings.news_refresh_interval_hours)

    async def ensure_ticker_news(self, ticker: str, market: str, force: bool = False) -> list:
        """Return cached news for a ticker, fetching fresh data when stale/forced.

        Falls back to the last cached articles if the fetch fails so the feed
        never breaks because of a yfinance hiccup.
        """
        cached = await self.cache_repo.get_by_ticker(ticker)
        if not force and cached and not self._is_stale(cached):
            return cached.get("news") or []

        fresh = await self.fetch_ticker_news(ticker, market)
        if fresh:
            try:
                await self.cache_repo.upsert(ticker, fresh)
                logger.info("[news] Cached %d articles for %s", len(fresh), ticker)
                return fresh
            except Exception as exc:
                logger.error("[news] Failed to persist cache for %s: %s", ticker, exc)
                return fresh
        if cached:
            logger.info("[news] Fetch failed for %s; serving stale cache", ticker)
            return cached.get("news") or []
        return []

    # ------------------------------------------------------------------
    # User feed
    # ------------------------------------------------------------------

    async def get_news_for_user(self, user_id: str, force: bool = False) -> dict:
        """Build the personalized news feed for a user.

        Returns {"items": [...], "fetched_at": str|None, "interests": [...]}.
        """
        interests = await self.interest_repo.get_by_user_id(user_id)
        tickers = [i.get("ticker", "") for i in interests if i.get("ticker")]
        market_by_ticker = {i.get("ticker", "").upper(): i.get("market", "US") for i in interests}

        results = await asyncio.gather(
            *[
                self.ensure_ticker_news(t, market_by_ticker.get(t.upper(), "US"), force=force)
                for t in tickers
            ],
            return_exceptions=True,
        )

        items = []
        for idx, (ticker, result) in enumerate(zip(tickers, results)):
            if isinstance(result, Exception):
                logger.warning("[news] Skipping %s after error: %s", ticker, result)
                continue
            for i, article in enumerate(result or []):
                company = article.get("company") or ticker
                items.append({
                    "id": f"{ticker}-news-{i}",
                    "ticker": ticker,
                    "company": company,
                    "headline": article.get("headline", ""),
                    "summary": article.get("summary", ""),
                    "source": article.get("source", "Unknown"),
                    "url": article.get("url", ""),
                    "time": article.get("published_at", ""),
                    "sentiment": article.get("sentiment", "Neutral"),
                    "impact": article.get("impact", "Medium"),
                })

        def _sort_key(item: dict):
            try:
                return datetime.fromisoformat(str(item["time"]).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return datetime.min.replace(tzinfo=timezone.utc)

        items.sort(key=_sort_key, reverse=True)

        newest_fetch = await self._newest_fetched_at(tickers)
        return {
            "items": items,
            "fetched_at": newest_fetch,
            "interests": [t for t in tickers],
        }

    async def _newest_fetched_at(self, tickers: list) -> Optional[str]:
        """Return the most recent fetched_at among the user's tickers."""
        newest: Optional[datetime] = None
        for t in tickers:
            try:
                row = await self.cache_repo.get_by_ticker(t)
            except Exception:
                continue
            if not row or not row.get("fetched_at"):
                continue
            try:
                ts = datetime.fromisoformat(str(row["fetched_at"]).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if newest is None or ts > newest:
                newest = ts
        return newest.isoformat() if newest else None

    # ------------------------------------------------------------------
    # Interests
    # ------------------------------------------------------------------

    async def add_interest(self, user_id: str, ticker: str, market: str = "US", source: str = "watchlist") -> Optional[dict]:
        """Register a stock as an interest for the user."""
        t = (ticker or "").strip().upper()
        if not t:
            return None
        try:
            return await self.interest_repo.upsert(user_id, t, market or "US", source)
        except Exception as exc:
            logger.warning("[news] Failed to add interest %s for %s: %s", t, user_id, exc)
            return None

    async def remove_interest(self, user_id: str, ticker: str) -> bool:
        """Remove a stock from the user's interests."""
        try:
            return await self.interest_repo.remove_by_ticker(user_id, ticker)
        except Exception as exc:
            logger.warning("[news] Failed to remove interest %s for %s: %s", ticker, user_id, exc)
            return False

    async def sync_interests(self, user_id: str, items: list) -> int:
        """Bulk-register interests (first-load seed)."""
        try:
            return await self.interest_repo.sync(user_id, items)
        except Exception as exc:
            logger.warning("[news] Failed to sync interests for %s: %s", user_id, exc)
            return 0

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    async def refresh_all_interests(self) -> None:
        """Fetch fresh news for every distinct ticker across all users."""
        try:
            rows = await self.interest_repo.all_interests()
        except Exception as exc:
            logger.error("[news] Scheduler could not list interests: %s", exc)
            return

        unique: dict[str, str] = {}
        for row in rows:
            t = (row.get("ticker") or "").upper()
            if t:
                unique.setdefault(t, row.get("market") or "US")

        if not unique:
            logger.info("[news] Scheduler: no interests to refresh")
            return

        results = await asyncio.gather(
            *[self.ensure_ticker_news(t, m, force=True) for t, m in unique.items()],
            return_exceptions=True,
        )
        ok = sum(1 for r in results if not isinstance(r, Exception) and r)
        logger.info("[news] Scheduler refreshed %d/%d tickers", ok, len(unique))

    async def run_scheduler(self) -> None:
        """Background loop: refresh all interests every interval hours."""
        interval = timedelta(hours=self.settings.news_refresh_interval_hours)
        logger.info(
            "[news] Scheduler started (interval=%s)",
            self.settings.news_refresh_interval_hours,
        )
        while True:
            await asyncio.sleep(interval.total_seconds())
            try:
                await self.refresh_all_interests()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("[news] Scheduler cycle failed: %s", exc)
