from uuid import UUID

from pydantic import BaseModel


class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class DetectedItem(BaseModel):
    id: str
    bbox: BoundingBox
    category: str
    confidence: float


class SegmentResponse(BaseModel):
    items: list[DetectedItem]
    image_width: int
    image_height: int


class ListingResult(BaseModel):
    id: UUID
    image_url: str
    price: float | None
    currency: str
    size: str | None
    condition: str | None
    title: str | None
    platform: str
    listing_url: str
    similarity: float
    confidence_label: str


class SearchResponse(BaseModel):
    results: list[ListingResult]
    query_category: str | None = None
