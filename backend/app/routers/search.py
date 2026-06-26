from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.search import BoundingBox, SearchResponse, SegmentResponse
from app.services.embedding import generate_embedding
from app.services.segmentation import detect_garments
from app.services.vector_search import find_similar_listings

router = APIRouter(prefix="/api/v1/search", tags=["search"])

MAX_IMAGE_BYTES = settings.max_image_size_mb * 1024 * 1024
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


async def _read_upload_image(image: UploadFile) -> Image.Image:
    contents = await image.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"Image exceeds {settings.max_image_size_mb}MB limit")
    try:
        img = Image.open(BytesIO(contents))
    except Exception:
        raise HTTPException(400, "Invalid image file")

    if img.format not in ALLOWED_FORMATS:
        raise HTTPException(415, "Unsupported image format. Use JPEG, PNG, or WebP.")

    img = img.convert("RGB")

    max_dim = settings.max_image_dimension
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    return img


@router.post("/segment", response_model=SegmentResponse)
async def segment_image(
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    img = await _read_upload_image(image)
    items, width, height = await detect_garments(img)
    return SegmentResponse(items=items, image_width=width, image_height=height)


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
    img = await _read_upload_image(image)

    bbox = None
    if bbox_w > 0 and bbox_h > 0:
        bbox = BoundingBox(x=bbox_x, y=bbox_y, w=bbox_w, h=bbox_h)

    embedding = await generate_embedding(img, bbox)
    results = await find_similar_listings(
        db, embedding, limit=20, min_price=min_price, max_price=max_price,
    )

    return SearchResponse(results=results)
