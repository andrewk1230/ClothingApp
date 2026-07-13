import logging
from io import BytesIO
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import (
    RateLimitStatus,
    check_find_rate_limit,
    check_rate_limit,
)
from app.models.search_history import SearchHistory
from app.schemas.search import BoundingBox, SearchResponse, SegmentResponse
from app.services.embedding import generate_embedding
from app.services.segmentation import detect_garments
from app.services.vector_search import find_similar_listings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["search"])

MAX_IMAGE_BYTES = settings.max_image_size_mb * 1024 * 1024
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


async def _read_upload_image(image: UploadFile) -> Image.Image:
    contents = await image.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"Image exceeds {settings.max_image_size_mb}MB limit")
    try:
        img = Image.open(BytesIO(contents))
        fmt = img.format
        # Header is parsed at this point but pixels are not decoded yet:
        # reject decompression bombs (small file, huge bitmap) before load().
        if img.width * img.height > settings.max_image_pixels:
            raise HTTPException(413, "Image dimensions too large")
        # Image.open only parses the header; force a full decode here so that
        # truncated/corrupt files fail with a 400 instead of a 500 later.
        img.load()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Invalid image file")

    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(415, "Unsupported image format. Use JPEG, PNG, or WebP.")

    try:
        img = img.convert("RGB")
    except Exception:
        raise HTTPException(400, "Invalid image file")

    max_dim = settings.max_image_dimension
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    return img


@router.post("/segment", response_model=SegmentResponse)
async def segment_image(
    request: Request,
    response: Response,
    image: UploadFile = File(...),
    user_id: UUID | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate the upload BEFORE consuming a rate-limit unit: a rejected
    # image (too large / corrupt / wrong format) is not a search (PRD §4.5,
    # "1 upload = 1 search").
    img = await _read_upload_image(image)
    rate: RateLimitStatus = await check_rate_limit(request, user_id, db)
    items, width, height = await detect_garments(img)

    response.headers["X-RateLimit-Limit"] = str(rate.limit)
    response.headers["X-RateLimit-Remaining"] = str(rate.remaining)

    return SegmentResponse(items=items, image_width=width, image_height=height)


@router.post("/find", response_model=SearchResponse)
async def find_similar(
    request: Request,
    image: UploadFile = File(...),
    bbox_x: float = Query(0),
    bbox_y: float = Query(0),
    bbox_w: float = Query(0),
    bbox_h: float = Query(0),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    category: str | None = Query(None, max_length=50),
    user_id: UUID | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Abuse cap only (unmetered per PRD §4.5) — checked before any image
    # decoding or GPU work so over-cap callers cost nothing.
    await check_find_rate_limit(request, user_id, db)
    img = await _read_upload_image(image)

    bbox = None
    if bbox_w > 0 and bbox_h > 0:
        bbox = BoundingBox(x=bbox_x, y=bbox_y, w=bbox_w, h=bbox_h)

    embedding = await generate_embedding(img, bbox)
    results = await find_similar_listings(
        db, embedding, limit=20, min_price=min_price, max_price=max_price,
    )

    if user_id is not None:
        try:
            db.add(SearchHistory(
                user_id=user_id,
                category=category,
                bbox=bbox.model_dump() if bbox else None,
                result_ids=[r.id for r in results],
            ))
            await db.commit()
        except Exception:
            logger.warning(
                "Failed to log search history for user %s", user_id, exc_info=True,
            )
            await db.rollback()

    return SearchResponse(results=results, query_category=category)
