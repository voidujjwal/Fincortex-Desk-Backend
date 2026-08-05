from pydantic import BaseModel


class UsageResponse(BaseModel):
    used_today: int
    remaining: int
    daily_limit: int