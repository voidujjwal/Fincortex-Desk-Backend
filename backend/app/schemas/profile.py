from typing import Optional

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    id: Optional[str] = None
    user_id: str
    email: Optional[str] = None
    plan: str = "Free"
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProfileUpdate(BaseModel):
    plan: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None