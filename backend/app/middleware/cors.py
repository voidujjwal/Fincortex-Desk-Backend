"""CORS middleware for the FastAPI application."""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config.settings import get_settings


class CORSMiddleware(BaseHTTPMiddleware):
    """Simple CORS middleware that adds appropriate headers."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        origin = request.headers.get("origin", "")

        response = await call_next(request)

        for allowed_origin in settings.cors_origins:
            if allowed_origin == "*" or origin == allowed_origin:
                response.headers["Access-Control-Allow-Origin"] = (
                    allowed_origin if allowed_origin != "*" else "*"
                )
                response.headers["Access-Control-Allow-Methods"] = (
                    "GET, POST, PUT, DELETE, OPTIONS, WebSocket"
                )
                response.headers["Access-Control-Allow-Headers"] = (
                    "Authorization, Content-Type, Accept"
                )
                break

        return response


async def cors_preflight(request: Request, call_next):
    """Handle CORS preflight requests."""
    if request.method == "OPTIONS":
        return JSONResponse(status_code=204, content={})