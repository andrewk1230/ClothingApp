from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ListingCheckResponse(BaseModel):
    id: UUID
    active: bool


class SavedItemResponse(BaseModel):
    id: UUID
    listing_id: UUID
    image_url: str
    price: float | None
    currency: str
    platform: str
    listing_url: str
    title: str | None


class SearchHistoryEntry(BaseModel):
    id: UUID
    category: str | None
    bbox: dict | None
    result_count: int
    created_at: datetime
