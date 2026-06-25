from pathlib import Path

_model = None

CATEGORY_MAP = {
    0: "top",
    1: "outerwear",
    2: "bottom",
    3: "dress",
    4: "footwear",
    5: "bag",
    6: "hat",
    7: "jewelry",
    8: "eyewear",
    9: "scarf",
    10: "belt",
    11: "socks",
}


def load_yolo(weights_path: str):
    """Load YOLOv8 fashion detection model (singleton)."""
    global _model

    from ultralytics import YOLO

    path = Path(weights_path)
    if not path.exists():
        print(f"WARNING: YOLOv8 weights not found at {weights_path}. Segmentation disabled.")
        return

    _model = YOLO(str(path))
    print(f"YOLOv8 loaded from {weights_path}")


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
