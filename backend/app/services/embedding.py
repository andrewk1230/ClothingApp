import asyncio

from PIL import Image

from app.ml import clip_model
from app.schemas.search import BoundingBox


async def generate_embedding(image: Image.Image, bbox: BoundingBox | None = None) -> list[float]:
    if bbox:
        width, height = image.size
        left = max(0, int(bbox.x))
        top = max(0, int(bbox.y))
        right = min(width, int(bbox.x + bbox.w))
        bottom = min(height, int(bbox.y + bbox.h))
        if right > left and bottom > top:
            image = image.crop((left, top, right, bottom))

    # CLIP inference is synchronous CPU/GPU-bound work; run it off the event
    # loop so concurrent requests (and scheduler jobs) are not blocked.
    return await asyncio.to_thread(clip_model.encode_image, image)
