"""FastAPI application entry point."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import Settings, get_settings
from app.config.logging import setup_logging
from app.middleware.logging import RequestLoggingMiddleware
from app.database import get_supabase_client
from app.queue import AsyncioJobQueue
from app.services.analysis_service import AnalysisService
from app.services.news_service import NewsService
from app.websocket import ws_manager

# Import routes
from app.api.routes.analysis_routes import router as analysis_router
from app.api.routes.news_routes import router as news_router
from app.websocket.routes import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Load env vars so LLM clients can read API keys from os.environ
    load_dotenv()

    # Startup
    settings = get_settings()
    setup_logging(settings.log_level)

    logger = logging.getLogger("tradingagents")
    logger.info("Starting TradingAgents backend...")
    logger.info("Supabase URL: %s", settings.supabase_url[:30] + "...")

    # Initialize the job queue
    job_queue = AsyncioJobQueue()
    app.state.job_queue = job_queue

    # Initialize the analysis service
    app.state.analysis_service = AnalysisService(
        settings=settings,
        queue=job_queue,
    )

    # Initialize the news service and start the 4-hour refresh scheduler
    app.state.news_service = NewsService(settings=settings)
    app.state.news_scheduler_task = asyncio.create_task(
        app.state.news_service.run_scheduler()
    )

    logger.info("TradingAgents backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down TradingAgents backend...")
    scheduler_task = getattr(app.state, "news_scheduler_task", None)
    if scheduler_task is not None:
        scheduler_task.cancel()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="TradingAgents API",
        description="Multi-Agent LLM Financial Trading Framework API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Routes
    app.include_router(analysis_router, prefix="/api")
    app.include_router(news_router, prefix="/api")
    app.include_router(websocket_router, prefix="/ws")

    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()