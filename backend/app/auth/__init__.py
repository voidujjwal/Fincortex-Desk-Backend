from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.utils.jwt import verify_supabase_token, extract_token
from app.config.settings import get_settings

security = HTTPBearer(auto_error=False)


DEV_USER = {
    "id": "00000000-0000-0000-0000-000000000000",
    "email": "dev@tradeagents.app",
    "sub": "00000000-0000-0000-0000-000000000000",
    "plan": "pro",
}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify Supabase JWT token and return the user payload.

    Falls back to dev user if token is missing/invalid to allow seamless local execution.
    """
    token = extract_token(credentials.credentials if credentials else None)
    if not token:
        return DEV_USER

    settings = get_settings()
    payload = verify_supabase_token(token, settings)
    if payload is None:
        return DEV_USER

    return payload