from PIL import Image

from app.ml import yolo_model
from app.schemas.search import BoundingBox, DetectedItem

CONFIDENCE_THRESHOLD = 0.3


async def detect_garments(image: Image.Image) -> tuple[list[DetectedItem], int, int]:
    width, height = image.size
    raw_detections = yolo_model.detect(image, confidence_threshold=CONFIDENCE_THRESHOLD)

    items = []
    for i, det in enumerate(raw_detections):
        bbox_data = det["bbox"]
        items.append(DetectedItem(
            id=f"det_{i}",
            bbox=BoundingBox(
                x=bbox_data["x"], y=bbox_data["y"],
                w=bbox_data["w"], h=bbox_data["h"],
            ),
            category=det["category"],
            confidence=det["confidence"],
        ))

    return items, width, height
