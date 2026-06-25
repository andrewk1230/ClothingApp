from PIL import Image

from app.schemas.search import BoundingBox, DetectedItem

CONFIDENCE_THRESHOLD = 0.3


async def detect_garments(image: Image.Image) -> tuple[list[DetectedItem], int, int]:
    """Run YOLOv8 inference to detect garments in an image.

    Returns detected items and image dimensions.
    """
    # TODO: Phase 1 — load YOLOv8 model, run inference, map class IDs to categories
    width, height = image.size
    return [], width, height
