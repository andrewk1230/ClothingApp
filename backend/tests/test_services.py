"""Unit tests for the embedding/segmentation service layer (ML mocked)."""

import pytest
from PIL import Image

from app.schemas.search import BoundingBox
from app.services.embedding import generate_embedding
from app.services.segmentation import detect_garments
from tests.conftest import unit_embedding


@pytest.fixture
def capture_encode(monkeypatch):
    captured = {}

    def fake_encode(image):
        captured["size"] = image.size
        return unit_embedding()

    monkeypatch.setattr("app.services.embedding.clip_model.encode_image", fake_encode)
    return captured


def _img(width=100, height=80) -> Image.Image:
    return Image.new("RGB", (width, height), "blue")


async def test_generate_embedding_no_bbox_uses_full_image(capture_encode):
    result = await generate_embedding(_img())
    assert result == unit_embedding()
    assert capture_encode["size"] == (100, 80)


async def test_generate_embedding_crops_to_bbox(capture_encode):
    await generate_embedding(_img(), BoundingBox(x=10, y=20, w=30, h=40))
    assert capture_encode["size"] == (30, 40)


async def test_generate_embedding_clamps_out_of_bounds_bbox(capture_encode):
    # Extends past both edges -> clamped to image bounds.
    await generate_embedding(_img(), BoundingBox(x=-10, y=-10, w=500, h=500))
    assert capture_encode["size"] == (100, 80)


async def test_generate_embedding_degenerate_bbox_falls_back_to_full_image(
    capture_encode,
):
    # Fully outside the image -> zero-area crop -> use the whole image.
    await generate_embedding(_img(), BoundingBox(x=200, y=200, w=50, h=50))
    assert capture_encode["size"] == (100, 80)


async def test_detect_garments_maps_detections(monkeypatch):
    def fake_detect(image, confidence_threshold):
        assert confidence_threshold == 0.3
        return [
            {
                "bbox": {"x": 1.0, "y": 2.0, "w": 3.0, "h": 4.0},
                "category": "top",
                "confidence": 0.85,
            }
        ]

    monkeypatch.setattr("app.services.segmentation.yolo_model.detect", fake_detect)

    items, width, height = await detect_garments(_img())
    assert (width, height) == (100, 80)
    assert len(items) == 1
    assert items[0].id == "det_0"
    assert items[0].category == "top"
    assert items[0].confidence == 0.85
    assert (items[0].bbox.x, items[0].bbox.y) == (1.0, 2.0)
