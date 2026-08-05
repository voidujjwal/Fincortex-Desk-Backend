"""Pydantic schemas for the personalized news feed."""

from typing import List, Optional

from pydantic import BaseModel, Field


class NewsItemSchema(BaseModel):
    """A single news article shaped for the frontend NewsFeed."""

    id: str
    ticker: str
    company: str = ""
    headline: str
    summary: str = ""
    source: str = "Unknown"
    url: str = ""
    time: str = ""
    sentiment: str = "Neutral"
    impact: str = "Medium"


class NewsResponse(BaseModel):
    """GET /api/news response."""

    items: List[NewsItemSchema] = []
    fetched_at: Optional[str] = None
    interests: List[str] = []


class InterestRequest(BaseModel):
    """Add an interest for the current user."""

    ticker: str = Field(..., min_length=1, max_length=10)
    market: str = Field(default="US", description="US | India | Crypto | Forex")
    source: str = Field(default="watchlist", description="watchlist | research")


class InterestSyncItem(BaseModel):
    """One ticker in a bulk interest sync."""

    ticker: str = Field(..., min_length=1, max_length=10)
    market: str = Field(default="US")
    source: str = Field(default="watchlist")


class InterestSyncRequest(BaseModel):
    """Bulk sync of interests (first-load seed)."""

    tickers: List[InterestSyncItem] = []


class InterestResponse(BaseModel):
    """Response after adding/removing/syncing interests."""

    ok: bool = True
    ticker: Optional[str] = None
    count: Optional[int] = None
