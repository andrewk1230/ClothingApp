import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None

# DeepFashion2 class IDs → our simplified taxonomy
DEEPFASHION2_MAP = {
    0: "top",           # short_sleeve_top
    1: "top",           # long_sleeve_top
    2: "outerwear",     # short_sleeve_outwear
    3: "outerwear",     # long_sleeve_outwear
    4: "top",           # vest
    5: "top",           # sling
    6: "bottom",        # shorts
    7: "bottom",        # trousers
    8: "bottom",        # skirt
    9: "dress",         # short_sleeve_dress
    10: "dress",        # long_sleeve_dress
    11: "dress",        # vest_dress
    12: "dress",        # sling_dress
}

CATEGORY_MAP = DEEPFASHION2_MAP


def load_yolo(weights_path: str):
    """Load YOLOv8 fashion detection model (singleton)."""
    global _model

    from ultralytics import YOLO

    path = Path(weights_path)
    if not path.exists():
        logger.warning("YOLOv8 weights not found at %s. Segmentation disabled.", weights_path)
        return

    _model = YOLO(str(path))
    logger.info("YOLOv8 loaded from %s", weights_path)


def detect(image, confidence_threshold: float = 0.3) -> list[dict]:
    """Run YOLOv8 inference on a PIL image. Returns list of detections."""
    if _model is None:
        return []

    results = _model(image, verbose=False)
    detections = []

    for result in results:
        for box in result.boxes:
            conf = float(box.conf[0])
            if conf < confidence_threshold:
                continue

            cls_id = int(box.cls[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append({
                "bbox": {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1},
                "category": CATEGORY_MAP.get(cls_id, "unknown"),
                "confidence": conf,
            })

    return detections
