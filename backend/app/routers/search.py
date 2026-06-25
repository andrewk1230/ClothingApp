from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.search import SearchResponse, SegmentResponse

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("/segment", response_model=SegmentResponse)
async def segment_image(
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image and detect garment bounding boxes."""
    # TODO: Phase 1 — integrate YOLOv8 segmentation service
    # TODO: Phase 5 — rate limiting middleware
    return SegmentResponse(items=[], image_width=0, image_height=0)


@router.post("/find", response_model=SearchResponse)
async def find_similar(
    image: UploadFile = File(...),
    bbox_x: float = Query(0),
    bbox_y: float = Query(0),
    bbox_w: float = Query(0),
    bbox_h: float = Query(0),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Find visually similar listings for a cropped garment region."""
    # TODO: Phase 4 — crop image, generate CLIP embedding, query pgvector
    return SearchResponse(results=[])
