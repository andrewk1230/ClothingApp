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
    size: str | None
    condition: str | None
    title: str | None
    platform: str
    listing_url: str
    created_at: datetime


class HistoryResultListing(BaseModel):
    id: UUID
    image_url: str
    price: float | None
    currency: str
    size: str | None
    condition: str | None
    title: str | None
    platform: str
    listing_url: str
    active: bool


class SearchHistoryEntry(BaseModel):
    id: UUID
    category: str | None
    bbox: dict | None
    result_count: int
    thumbnail_urls: list[str] = []
    created_at: datetime
