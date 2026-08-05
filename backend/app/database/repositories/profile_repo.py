"""Repository for the profiles table."""

from typing import Optional
from app.database.repositories.base import BaseRepository


class ProfileRepository(BaseRepository):
    """Repository for profiles table."""

    def __init__(self, client):
        super().__init__(client, "profiles")

    async def get_by_user_id(self, user_id: str) -> Optional[dict]:
        """Fetch a profile by user id (profiles.id = auth.users.id)."""
        result = self._table.select("*").eq("id", user_id).execute()
        if result.data:
            return result.data[0]
        return None

    async def get_by_email(self, email: str) -> Optional[dict]:
        """Fetch a profile by email."""
        result = self._table.select("*").eq("email", email).execute()
        if result.data:
            return result.data[0]
        return None

    async def ensure_exists(self, user_id: str, email: str = "") -> dict:
        """Create a profile row if it doesn't exist. Returns the profile."""
        existing = self._table.select("*").eq("id", user_id).execute()
        if existing.data:
            return existing.data[0]
        data = {"id": user_id}
        if email:
            data["email"] = email
        result = self._table.insert(data).execute()
        if result.data:
            return result.data[0]
        raise RuntimeError(f"Failed to create profile for {user_id}")