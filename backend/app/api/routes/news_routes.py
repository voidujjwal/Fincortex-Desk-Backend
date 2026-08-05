"""REST API routes for the personalized news feed."""

from fastapi import APIRouter, Depends, Request

from app.auth import get_current_user
from app.schemas import (
    NewsResponse,
    InterestRequest,
    InterestSyncRequest,
    InterestResponse,
)
from app.services.news_service import NewsService

router = APIRouter(tags=["news"])


def get_news_service(request: Request) -> NewsService:
    """Dependency injection for NewsService from app state."""
    try:
        service = request.app.state.news_service
    except AttributeError:
        service = None
    if service is None:
        service = NewsService()
    return service


@router.get("/news", response_model=NewsResponse)
async def get_news(
    refresh: bool = False,
    service: NewsService = Depends(get_news_service),
    user: dict = Depends(get_current_user),
):
    """Get the personalized news feed for the current user.

    refresh=true forces a fresh yfinance fetch for the user's interests.
    """
    user_id = user.get("id", user.get("sub", "unknown"))
    return await service.get_news_for_user(user_id, force=refresh)


@router.post("/interests", response_model=InterestResponse)
async def add_interest(
    body: InterestRequest,
    service: NewsService = Depends(get_news_service),
    user: dict = Depends(get_current_user),
):
    """Register a stock as an interest (watchlist add or research)."""
    user_id = user.get("id", user.get("sub", "unknown"))
    result = await service.add_interest(user_id, body.ticker, body.market, body.source)
    return InterestResponse(ok=result is not None, ticker=body.ticker.upper())


@router.post("/interests/sync", response_model=InterestResponse)
async def sync_interests(
    body: InterestSyncRequest,
    service: NewsService = Depends(get_news_service),
    user: dict = Depends(get_current_user),
):
    """Bulk-register interests (first-load seed from the default watchlist)."""
    user_id = user.get("id", user.get("sub", "unknown"))
    items = [
        {"ticker": t.ticker, "market": t.market, "source": t.source}
        for t in body.tickers
    ]
    count = await service.sync_interests(user_id, items)
    return InterestResponse(ok=True, count=count)


@router.delete("/interests/{ticker}", response_model=InterestResponse)
async def remove_interest(
    ticker: str,
    service: NewsService = Depends(get_news_service),
    user: dict = Depends(get_current_user),
):
    """Remove a stock from the user's interests."""
    user_id = user.get("id", user.get("sub", "unknown"))
    await service.remove_interest(user_id, ticker)
    return InterestResponse(ok=True, ticker=ticker.upper())
