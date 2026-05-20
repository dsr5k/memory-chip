from uuid import UUID

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    session_id: UUID | None = None
    top_k: int = 5


class SearchHit(BaseModel):
    id: str
    score: float
    payload: dict
