"""JWT utility for Supabase authentication verification."""

import logging
from typing import Optional, Dict, Any

import jwt as pyjwt

from app.config.settings import Settings, get_settings

logger = logging.getLogger("tradingagents.auth")


def verify_supabase_token(
    token: str, settings: Optional[Settings] = None
) -> Optional[Dict[str, Any]]:
    """Verify a Supabase JWT token and return the user payload.

    Uses Supabase service role key to validate the token via
    the supabase-py client, then decodes the JWT payload to
    extract claims (sub, email, app_metadata, etc.).
    """
    if settings is None:
        settings = get_settings()

    try:
        from supabase import create_client

        supabase = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        user_response = supabase.auth.get_user(token)
        if user_response is None or user_response.user is None:
            logger.warning("JWT verification failed: no user returned")
            return None
        logger.info("JWT verified for user: %s", user_response.user.id)

    except Exception as exc:
        logger.error("JWT supabase auth check failed: %s", exc)
        return None

    try:
        payload = pyjwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=["RS256", "ES256"],
        )
        return payload
    except pyjwt.DecodeError as exc:
        logger.error("JWT decode failed: %s", exc)
        return None


def extract_token(authorization: Optional[str]) -> Optional[str]:
    """Extract the Bearer token from an Authorization header."""
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return authorization