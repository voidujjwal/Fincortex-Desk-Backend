from typing import Optional

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    id: Optional[str] = None
    user_id: str
    theme: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    default_models: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    default_models: Optional[dict] = None