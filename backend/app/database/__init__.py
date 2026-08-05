import logging
from typing import Optional
from supabase import create_client, Client
from app.config.settings import Settings, get_settings

logger = logging.getLogger("tradingagents.db")

_client: Optional[Client] = None


def get_supabase_client(settings: Optional[Settings] = None) -> Client:
    """Get or create a Supabase client instance."""
    global _client
    if _client is None:
        s = settings or get_settings()
        _client = create_client(s.supabase_url, s.supabase_service_role_key)
        logger.info("Supabase client initialized for %s", s.supabase_url[:30])
    return _client


def reset_supabase_client() -> None:
    """Reset the Supabase client (useful for testing)."""
    global _client
    _client = None
    logger.info("Supabase client reset")