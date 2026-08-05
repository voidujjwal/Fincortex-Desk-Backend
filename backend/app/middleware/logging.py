"""Request logging middleware."""

import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("tradingagents.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log incoming requests and their duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        logger.info(
            "Request: %s %s", request.method, request.url.path
        )

        response = await call_next(request)

        duration = time.time() - start
        logger.info(
            "Response: %s %s %d (%.3fs)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )

        return response