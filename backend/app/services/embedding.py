from PIL import Image

from app.ml import clip_model
from app.schemas.search import BoundingBox


async def generate_embedding(image: Image.Image, bbox: BoundingBox | None = None) -> list[float]:
    if bbox:
        image = image.crop((
            int(bbox.x),
            int(bbox.y),
            int(bbox.x + bbox.w),
            int(bbox.y + bbox.h),
        ))

    return clip_model.encode_image(image)
