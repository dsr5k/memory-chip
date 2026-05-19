from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    user_id: UUID


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    started_at: datetime
    ended_at: datetime | None

    class Config:
        from_attributes = True
