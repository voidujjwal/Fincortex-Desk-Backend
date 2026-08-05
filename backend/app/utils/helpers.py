"""Utility helpers for the backend application."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def generate_job_id() -> str:
    """Generate a unique job identifier (UUID4 string)."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely get a nested value from a dictionary."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return default
        if data is None:
            return default
    return data


def paginate(
    items: list, page: int = 1, page_size: int = 20
) -> dict:
    """Return paginated slice of items with metadata."""
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    slice_ = items[start:end]
    return {
        "items": slice_,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }