import numpy as np
from PIL import Image

from app.schemas.search import BoundingBox


async def generate_embedding(image: Image.Image, bbox: BoundingBox | None = None) -> list[float]:
    """Generate a CLIP embedding for an image region.

    If bbox is provided, crops the image to that region first.
    Returns a 512-dimensional embedding vector.
    """
    if bbox:
        image = image.crop((
            int(bbox.x),
            int(bbox.y),
            int(bbox.x + bbox.w),
            int(bbox.y + bbox.h),
        ))

    # TODO: Phase 1 — load CLIP model, preprocess image, run inference
    return [0.0] * 512
