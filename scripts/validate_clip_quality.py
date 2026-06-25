#!/usr/bin/env python3
"""
validate_clip_quality.py -- GrailSeeker CLIP Visual Search Quality Validation

Validates whether CLIP ViT-B/32 produces good enough similarity scores for
second-hand fashion visual search. Also benchmarks FashionCLIP if available.

Usage:
    python validate_clip_quality.py                    # CPU, vanilla CLIP only
    python validate_clip_quality.py --device cuda      # GPU
    python validate_clip_quality.py --include-fashion   # also test FashionCLIP
    python validate_clip_quality.py --image-dir ./imgs  # use real images from disk

Requirements:
    pip install open-clip-torch torch Pillow numpy

Optional (for FashionCLIP comparison):
    pip install transformers
"""

from __future__ import annotations

import argparse
import io
import math
import os
import sys
import textwrap
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# 1. Synthetic test-image generation
# ---------------------------------------------------------------------------

# Colors used to simulate garment palettes
PALETTE = {
    "red":        (200, 40, 40),
    "maroon":     (128, 20, 20),
    "black":      (25, 25, 25),
    "dark_blue":  (20, 30, 80),
    "light_blue": (100, 160, 220),
    "white":      (240, 240, 240),
    "olive":      (107, 142, 35),
    "beige":      (210, 190, 160),
    "pink":       (220, 130, 150),
    "orange":     (220, 130, 40),
    "grey":       (140, 140, 140),
    "brown":      (120, 70, 30),
    "green":      (34, 120, 50),
    "sky":        (135, 206, 235),
    "landscape":  (80, 160, 80),      # greenish for landscape
    "sunset":     (220, 120, 60),     # orange sky
}


def _draw_jacket_shape(draw: ImageDraw.ImageDraw, w: int, h: int, color: tuple):
    """Draw a rough jacket silhouette."""
    cx, cy = w // 2, h // 2
    # torso
    draw.rectangle([cx - 60, cy - 70, cx + 60, cy + 80], fill=color)
    # left sleeve
    draw.polygon([(cx - 60, cy - 60), (cx - 100, cy + 30),
                  (cx - 80, cy + 40), (cx - 50, cy - 40)], fill=color)
    # right sleeve
    draw.polygon([(cx + 60, cy - 60), (cx + 100, cy + 30),
                  (cx + 80, cy + 40), (cx + 50, cy - 40)], fill=color)
    # collar
    draw.polygon([(cx - 30, cy - 70), (cx, cy - 90),
                  (cx + 30, cy - 70)], fill=color)


def _draw_pants_shape(draw: ImageDraw.ImageDraw, w: int, h: int, color: tuple):
    """Draw a rough pants/jeans silhouette."""
    cx, cy = w // 2, h // 2
    # waistband
    draw.rectangle([cx - 55, cy - 80, cx + 55, cy - 60], fill=color)
    # left leg
    draw.rectangle([cx - 55, cy - 60, cx - 5, cy + 90], fill=color)
    # right leg
    draw.rectangle([cx + 5, cy - 60, cx + 55, cy + 90], fill=color)


def _draw_shoe_shape(draw: ImageDraw.ImageDraw, w: int, h: int, color: tuple):
    """Draw a rough sneaker/shoe silhouette."""
    cx, cy = w // 2, h // 2
    draw.ellipse([cx - 70, cy - 25, cx + 70, cy + 35], fill=color)
    draw.rectangle([cx - 70, cy - 25, cx + 20, cy + 5], fill=color)
    # sole
    darker = tuple(max(0, c - 40) for c in color)
    draw.rectangle([cx - 75, cy + 25, cx + 75, cy + 40], fill=darker)


def _draw_tshirt_shape(draw: ImageDraw.ImageDraw, w: int, h: int, color: tuple):
    """Draw a rough t-shirt silhouette."""
    cx, cy = w // 2, h // 2
    # torso
    draw.rectangle([cx - 55, cy - 50, cx + 55, cy + 80], fill=color)
    # left sleeve (short)
    draw.polygon([(cx - 55, cy - 45), (cx - 90, cy - 10),
                  (cx - 75, cy + 5), (cx - 55, cy - 20)], fill=color)
    # right sleeve (short)
    draw.polygon([(cx + 55, cy - 45), (cx + 90, cy - 10),
                  (cx + 75, cy + 5), (cx + 55, cy - 20)], fill=color)
    # neckline
    draw.ellipse([cx - 20, cy - 60, cx + 20, cy - 40], fill=(255, 255, 255))


def _draw_landscape(draw: ImageDraw.ImageDraw, w: int, h: int):
    """Draw a simple landscape (non-clothing control image)."""
    # sky
    draw.rectangle([0, 0, w, h // 2], fill=PALETTE["sky"])
    # sun
    draw.ellipse([w - 80, 20, w - 30, 70], fill=(255, 220, 60))
    # ground
    draw.rectangle([0, h // 2, w, h], fill=PALETTE["landscape"])
    # mountain
    draw.polygon([(w // 4, h // 2), (w // 2, h // 5), (3 * w // 4, h // 2)],
                 fill=(120, 120, 140))


def _draw_car(draw: ImageDraw.ImageDraw, w: int, h: int):
    """Draw a simple car (non-clothing control image)."""
    cx, cy = w // 2, h // 2
    # body
    draw.rectangle([cx - 80, cy - 15, cx + 80, cy + 30], fill=(180, 30, 30))
    # roof
    draw.polygon([(cx - 40, cy - 15), (cx - 20, cy - 45),
                  (cx + 40, cy - 45), (cx + 60, cy - 15)], fill=(180, 30, 30))
    # wheels
    draw.ellipse([cx - 60, cy + 20, cx - 35, cy + 45], fill=(40, 40, 40))
    draw.ellipse([cx + 35, cy + 20, cx + 60, cy + 45], fill=(40, 40, 40))
    # ground
    draw.rectangle([0, cy + 40, w, h], fill=(100, 100, 100))


def _add_texture(img: Image.Image, pattern: str = "plain") -> Image.Image:
    """Overlay a simple texture pattern to differentiate materials."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    if pattern == "leather":
        # subtle diagonal lines
        for i in range(-h, w + h, 8):
            draw.line([(i, 0), (i + h, h)], fill=(0, 0, 0, 30), width=1)
    elif pattern == "denim":
        # cross-hatch
        for i in range(0, max(w, h), 6):
            draw.line([(i, 0), (i, h)], fill=(0, 0, 0, 20), width=1)
            draw.line([(0, i), (w, i)], fill=(0, 0, 0, 20), width=1)
    elif pattern == "acid_wash":
        rng = np.random.RandomState(42)
        for _ in range(200):
            x, y = rng.randint(0, w), rng.randint(0, h)
            r = rng.randint(2, 6)
            draw.ellipse([x - r, y - r, x + r, y + r],
                         fill=(200, 200, 220, 60))
    elif pattern == "stripes":
        for i in range(0, w, 12):
            draw.rectangle([i, 0, i + 4, h], fill=(255, 255, 255, 50))
    return img


@dataclass
class SyntheticImage:
    """Describes a synthetic test image."""
    name: str
    category: str           # jacket, pants, shoe, tshirt, non-clothing
    style_tags: list[str]
    image: Image.Image = field(repr=False)


def generate_synthetic_images() -> list[SyntheticImage]:
    """Create ~25 synthetic garment + control images for testing."""
    size = (224, 224)
    images: list[SyntheticImage] = []

    def make(name, category, tags, draw_fn, bg=(255, 255, 255)):
        img = Image.new("RGBA", size, bg + (255,))
        d = ImageDraw.Draw(img)
        draw_fn(d, *size)
        img = img.convert("RGB")
        images.append(SyntheticImage(name, category, tags, img))

    def make_textured(name, category, tags, shape_fn, color, texture, bg=(255, 255, 255)):
        img = Image.new("RGBA", size, bg + (255,))
        d = ImageDraw.Draw(img)
        shape_fn(d, *size, color)
        img = _add_texture(img, texture)
        img = img.convert("RGB")
        images.append(SyntheticImage(name, category, tags, img))

    # --- Jackets (same category, varying style) ---
    make_textured("red_leather_jacket", "jacket",
                  ["red", "leather", "jacket"],
                  _draw_jacket_shape, PALETTE["red"], "leather")
    make_textured("maroon_leather_jacket", "jacket",
                  ["maroon", "leather", "jacket"],
                  _draw_jacket_shape, PALETTE["maroon"], "leather")
    make_textured("black_leather_jacket", "jacket",
                  ["black", "leather", "jacket"],
                  _draw_jacket_shape, PALETTE["black"], "leather")
    make_textured("olive_bomber_jacket", "jacket",
                  ["olive", "bomber", "jacket"],
                  _draw_jacket_shape, PALETTE["olive"], "plain")
    make_textured("beige_jacket", "jacket",
                  ["beige", "light", "jacket"],
                  _draw_jacket_shape, PALETTE["beige"], "plain")
    make_textured("denim_jacket_blue", "jacket",
                  ["blue", "denim", "jacket"],
                  _draw_jacket_shape, PALETTE["dark_blue"], "denim")
    make_textured("denim_jacket_light", "jacket",
                  ["light_blue", "denim", "jacket"],
                  _draw_jacket_shape, PALETTE["light_blue"], "denim")

    # --- Pants/Jeans ---
    make_textured("slim_dark_denim", "pants",
                  ["slim", "dark", "denim", "jeans"],
                  _draw_pants_shape, PALETTE["dark_blue"], "denim")
    make_textured("baggy_acid_wash", "pants",
                  ["baggy", "acid_wash", "denim", "jeans"],
                  _draw_pants_shape, PALETTE["light_blue"], "acid_wash")
    make_textured("black_jeans", "pants",
                  ["black", "slim", "jeans"],
                  _draw_pants_shape, PALETTE["black"], "denim")
    make_textured("beige_chinos", "pants",
                  ["beige", "chinos", "casual"],
                  _draw_pants_shape, PALETTE["beige"], "plain")
    make_textured("olive_cargo", "pants",
                  ["olive", "cargo", "pants"],
                  _draw_pants_shape, PALETTE["olive"], "plain")

    # --- T-shirts ---
    make_textured("white_tshirt", "tshirt",
                  ["white", "plain", "tshirt"],
                  _draw_tshirt_shape, PALETTE["white"], "plain")
    make_textured("black_tshirt", "tshirt",
                  ["black", "plain", "tshirt"],
                  _draw_tshirt_shape, PALETTE["black"], "plain")
    make_textured("striped_tshirt", "tshirt",
                  ["red", "striped", "tshirt"],
                  _draw_tshirt_shape, PALETTE["red"], "stripes")
    make_textured("pink_tshirt", "tshirt",
                  ["pink", "plain", "tshirt"],
                  _draw_tshirt_shape, PALETTE["pink"], "plain")

    # --- Shoes ---
    make_textured("white_sneakers", "shoe",
                  ["white", "sneaker", "shoe"],
                  _draw_shoe_shape, PALETTE["white"], "plain",
                  bg=(200, 200, 200))
    make_textured("black_sneakers", "shoe",
                  ["black", "sneaker", "shoe"],
                  _draw_shoe_shape, PALETTE["black"], "plain",
                  bg=(200, 200, 200))
    make_textured("brown_boots", "shoe",
                  ["brown", "boot", "shoe"],
                  _draw_shoe_shape, PALETTE["brown"], "leather",
                  bg=(200, 200, 200))
    make_textured("red_sneakers", "shoe",
                  ["red", "sneaker", "shoe"],
                  _draw_shoe_shape, PALETTE["red"], "plain",
                  bg=(200, 200, 200))

    # --- Non-clothing controls ---
    make("landscape_photo", "non-clothing",
         ["landscape", "nature", "outdoor"],
         _draw_landscape)
    make("car_photo", "non-clothing",
         ["car", "vehicle", "red"],
         _draw_car)

    # plain color blocks (extra controls)
    for cname in ["red", "dark_blue", "green"]:
        img = Image.new("RGB", size, PALETTE[cname])
        images.append(SyntheticImage(
            f"solid_{cname}_block", "non-clothing",
            ["color_block", cname], img))

    return images


# ---------------------------------------------------------------------------
# 2. Real image loading (optional)
# ---------------------------------------------------------------------------

# Populate these with real image URLs for stronger validation.
# The script works without them -- synthetic images run by default.
REAL_IMAGE_URLS: dict[str, dict] = {
    # "red_leather_jacket_real": {
    #     "url": "https://example.com/red-jacket.jpg",
    #     "category": "jacket",
    #     "tags": ["red", "leather", "jacket"],
    # },
    # "vintage_denim_jacket_real": {
    #     "url": "https://example.com/denim-jacket.jpg",
    #     "category": "jacket",
    #     "tags": ["blue", "denim", "vintage", "jacket"],
    # },
    # Add more as needed...
}


def download_real_images() -> list[SyntheticImage]:
    """Download real images from REAL_IMAGE_URLS. Returns empty list if none configured."""
    results = []
    if not REAL_IMAGE_URLS:
        return results
    print("\n  Downloading real test images...")
    for name, meta in REAL_IMAGE_URLS.items():
        url = meta["url"]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GrailSeeker-Validator/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).convert("RGB").resize((224, 224))
            results.append(SyntheticImage(name, meta["category"], meta["tags"], img))
            print(f"    OK  {name}")
        except Exception as e:
            print(f"    FAIL {name}: {e}")
    return results


def load_images_from_dir(path: str) -> list[SyntheticImage]:
    """Load images from a directory. Names inferred from filenames."""
    results = []
    p = Path(path)
    if not p.is_dir():
        print(f"  Warning: --image-dir {path} does not exist, skipping.")
        return results
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            try:
                img = Image.open(f).convert("RGB").resize((224, 224))
                name = f.stem
                # Try to infer category from filename
                cat = "unknown"
                for kw in ("jacket", "pants", "jeans", "denim", "shoe",
                           "sneaker", "boot", "tshirt", "shirt", "hoodie"):
                    if kw in name.lower():
                        cat = {"jeans": "pants", "denim": "pants",
                               "sneaker": "shoe", "boot": "shoe",
                               "shirt": "tshirt", "hoodie": "tshirt"
                               }.get(kw, kw)
                        break
                results.append(SyntheticImage(name, cat, [name], img))
                print(f"    Loaded {name} (category={cat})")
            except Exception as e:
                print(f"    Failed to load {f.name}: {e}")
    return results


# ---------------------------------------------------------------------------
# 3. CLIP embedding
# ---------------------------------------------------------------------------

def load_clip_model(device: str):
    """Load OpenCLIP ViT-B/32 and return (model, preprocess, tokenizer)."""
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model = model.to(device).eval()
    return model, preprocess, tokenizer


def load_fashion_clip(device: str):
    """Load FashionCLIP (patrickjohncyh/fashion-clip) via transformers.
    Returns (model, processor) or (None, None) if unavailable."""
    try:
        from transformers import CLIPModel, CLIPProcessor
        model_id = "patrickjohncyh/fashion-clip"
        print(f"  Loading FashionCLIP ({model_id})...")
        processor = CLIPProcessor.from_pretrained(model_id)
        model = CLIPModel.from_pretrained(model_id).to(device).eval()
        return model, processor
    except ImportError:
        print("  transformers not installed -- skipping FashionCLIP.")
        return None, None
    except Exception as e:
        print(f"  Could not load FashionCLIP: {e}")
        return None, None


@torch.no_grad()
def embed_images_clip(model, preprocess, images: list[Image.Image],
                      device: str) -> np.ndarray:
    """Embed a batch of PIL images using OpenCLIP. Returns (N, D) normalized."""
    tensors = torch.stack([preprocess(img) for img in images]).to(device)
    feats = model.encode_image(tensors)
    feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy()


@torch.no_grad()
def embed_texts_clip(model, tokenizer, texts: list[str],
                     device: str) -> np.ndarray:
    """Embed text prompts using OpenCLIP. Returns (N, D) normalized."""
    tokens = tokenizer(texts).to(device)
    feats = model.encode_text(tokens)
    feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy()


@torch.no_grad()
def embed_images_fashion_clip(model, processor, images: list[Image.Image],
                              device: str) -> np.ndarray:
    """Embed images using FashionCLIP (HuggingFace transformers)."""
    inputs = processor(images=images, return_tensors="pt", padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    feats = model.get_image_features(**inputs)
    feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy()


@torch.no_grad()
def embed_texts_fashion_clip(model, processor, texts: list[str],
                             device: str) -> np.ndarray:
    """Embed texts using FashionCLIP."""
    inputs = processor(text=texts, return_tensors="pt", padding=True,
                       truncation=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    feats = model.get_text_features(**inputs)
    feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy()


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalized vectors."""
    return float(np.dot(a, b))


# ---------------------------------------------------------------------------
# 4. Test scenarios
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    name: str
    image_a: str
    image_b: str
    expected_band: str   # HIGH, MODERATE, LOW, VERY_LOW
    description: str


@dataclass
class TextImageTestCase:
    name: str
    text_prompt: str
    image_name: str
    expected_band: str
    description: str


THRESHOLDS = {
    "HIGH":      (0.70, 1.00),
    "MODERATE":  (0.40, 0.70),
    "LOW":       (0.20, 0.40),
    "VERY_LOW":  (0.00, 0.20),
}

# For synthetic images, CLIP scores will be lower than for real photos.
# We use relaxed thresholds to account for the simplicity of generated images.
SYNTHETIC_THRESHOLDS = {
    "HIGH":      (0.55, 1.00),
    "MODERATE":  (0.30, 0.70),
    "LOW":       (0.15, 0.40),
    "VERY_LOW":  (0.00, 0.20),
}

IMAGE_PAIR_TESTS = [
    # Same category, very similar style --> HIGH
    TestCase("similar_leather_jackets",
             "red_leather_jacket", "maroon_leather_jacket",
             "HIGH",
             "Red vs. maroon leather jacket (same category, similar style)"),
    TestCase("similar_dark_jackets",
             "black_leather_jacket", "maroon_leather_jacket",
             "HIGH",
             "Black vs. maroon leather jacket (dark leather jackets)"),
    TestCase("similar_denim_jackets",
             "denim_jacket_blue", "denim_jacket_light",
             "HIGH",
             "Dark vs. light denim jacket"),
    TestCase("similar_sneakers",
             "white_sneakers", "black_sneakers",
             "HIGH",
             "White vs. black sneakers (same silhouette)"),
    TestCase("similar_plain_tshirts",
             "white_tshirt", "black_tshirt",
             "HIGH",
             "White vs. black plain t-shirt"),

    # Same category, different style --> MODERATE
    TestCase("different_style_denim",
             "slim_dark_denim", "baggy_acid_wash",
             "MODERATE",
             "Slim dark jeans vs. baggy acid-wash (same cat, diff style)"),
    TestCase("leather_vs_denim_jacket",
             "black_leather_jacket", "denim_jacket_blue",
             "MODERATE",
             "Black leather jacket vs. blue denim jacket"),
    TestCase("different_pants",
             "black_jeans", "beige_chinos",
             "MODERATE",
             "Black jeans vs. beige chinos"),
    TestCase("sneaker_vs_boot",
             "white_sneakers", "brown_boots",
             "MODERATE",
             "White sneakers vs. brown boots (both footwear)"),

    # Different category --> LOW
    TestCase("jacket_vs_sneaker",
             "red_leather_jacket", "white_sneakers",
             "LOW",
             "Red leather jacket vs. white sneakers (cross-category)"),
    TestCase("pants_vs_tshirt",
             "slim_dark_denim", "white_tshirt",
             "LOW",
             "Dark jeans vs. white t-shirt (cross-category)"),
    TestCase("jacket_vs_pants",
             "olive_bomber_jacket", "olive_cargo",
             "LOW",
             "Olive jacket vs. olive cargo pants (same color, diff category)"),

    # Non-clothing vs clothing --> VERY LOW
    TestCase("landscape_vs_jacket",
             "landscape_photo", "red_leather_jacket",
             "VERY_LOW",
             "Landscape photo vs. red jacket (non-clothing vs. clothing)"),
    TestCase("car_vs_sneaker",
             "car_photo", "white_sneakers",
             "VERY_LOW",
             "Car vs. white sneakers (non-clothing vs. clothing)"),
    TestCase("color_block_vs_jacket",
             "solid_red_block", "red_leather_jacket",
             "VERY_LOW",
             "Solid red block vs. red jacket (control)"),
]

TEXT_IMAGE_TESTS = [
    TextImageTestCase("text_red_leather_jacket",
                      "a red leather jacket",
                      "red_leather_jacket",
                      "HIGH",
                      "Text 'red leather jacket' vs red leather jacket image"),
    TextImageTestCase("text_denim_jacket",
                      "a vintage oversized denim jacket",
                      "denim_jacket_blue",
                      "HIGH",
                      "Text 'vintage denim jacket' vs blue denim jacket image"),
    TextImageTestCase("text_white_sneakers",
                      "white sneakers",
                      "white_sneakers",
                      "HIGH",
                      "Text 'white sneakers' vs white sneaker image"),
    TextImageTestCase("text_black_tshirt",
                      "a plain black t-shirt",
                      "black_tshirt",
                      "HIGH",
                      "Text 'black t-shirt' vs black t-shirt image"),

    # Cross-category text-image (should be low)
    TextImageTestCase("text_jacket_vs_shoe_img",
                      "a leather jacket",
                      "white_sneakers",
                      "LOW",
                      "Text 'leather jacket' vs sneaker image"),
    TextImageTestCase("text_dress_vs_pants_img",
                      "an elegant evening dress",
                      "slim_dark_denim",
                      "LOW",
                      "Text 'evening dress' vs jeans image"),

    # Non-clothing text vs clothing image
    TextImageTestCase("text_landscape_vs_jacket",
                      "a beautiful mountain landscape at sunset",
                      "red_leather_jacket",
                      "VERY_LOW",
                      "Text 'landscape' vs jacket image"),
]


# ---------------------------------------------------------------------------
# 5. Test runner and reporting
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    test_name: str
    description: str
    score: float
    expected_band: str
    actual_band: str
    passed: bool
    model_name: str


def score_to_band(score: float, thresholds: dict) -> str:
    """Map a cosine similarity score to a band label."""
    for band, (lo, hi) in thresholds.items():
        if lo <= score <= hi:
            return band
    # Edge case: negative scores
    return "VERY_LOW"


def band_ok(expected: str, actual: str) -> bool:
    """Check if actual band matches expected. Allow one band of slack."""
    order = ["VERY_LOW", "LOW", "MODERATE", "HIGH"]
    ei = order.index(expected)
    ai = order.index(actual)
    return abs(ei - ai) <= 1   # allow one band off


def run_image_pair_tests(
    image_embeddings: dict[str, np.ndarray],
    tests: list[TestCase],
    model_name: str,
    thresholds: dict,
) -> list[TestResult]:
    results = []
    for tc in tests:
        if tc.image_a not in image_embeddings or tc.image_b not in image_embeddings:
            print(f"    SKIP {tc.name}: missing image(s)")
            continue
        score = cosine_sim(image_embeddings[tc.image_a],
                           image_embeddings[tc.image_b])
        actual = score_to_band(score, thresholds)
        ok = band_ok(tc.expected_band, actual)
        results.append(TestResult(
            tc.name, tc.description, score, tc.expected_band, actual, ok, model_name
        ))
    return results


def run_text_image_tests(
    image_embeddings: dict[str, np.ndarray],
    text_embeddings: dict[str, np.ndarray],
    tests: list[TextImageTestCase],
    model_name: str,
    thresholds: dict,
) -> list[TestResult]:
    results = []
    for tc in tests:
        if tc.image_name not in image_embeddings:
            print(f"    SKIP {tc.name}: missing image")
            continue
        if tc.text_prompt not in text_embeddings:
            print(f"    SKIP {tc.name}: missing text embedding")
            continue
        score = cosine_sim(text_embeddings[tc.text_prompt],
                           image_embeddings[tc.image_name])
        actual = score_to_band(score, thresholds)
        ok = band_ok(tc.expected_band, actual)
        results.append(TestResult(
            tc.name, tc.description, score, tc.expected_band, actual, ok, model_name
        ))
    return results


def print_report(results: list[TestResult], model_name: str):
    """Print a formatted quality report."""
    w = 78
    print("\n" + "=" * w)
    print(f"  QUALITY REPORT: {model_name}")
    print("=" * w)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    pass_rate = passed / total if total else 0

    # Group by test type
    img_results = [r for r in results if not r.test_name.startswith("text_")]
    txt_results = [r for r in results if r.test_name.startswith("text_")]

    if img_results:
        print(f"\n  Image-Image Similarity Tests ({len(img_results)} tests)")
        print("  " + "-" * (w - 2))
        for r in img_results:
            status = "PASS" if r.passed else "FAIL"
            marker = " " if r.passed else "!"
            print(f"  {marker} [{status}] {r.description}")
            print(f"           Score: {r.score:.4f}  "
                  f"Expected: {r.expected_band:<10} Got: {r.actual_band}")

    if txt_results:
        print(f"\n  Text-Image Similarity Tests ({len(txt_results)} tests)")
        print("  " + "-" * (w - 2))
        for r in txt_results:
            status = "PASS" if r.passed else "FAIL"
            marker = " " if r.passed else "!"
            print(f"  {marker} [{status}] {r.description}")
            print(f"           Score: {r.score:.4f}  "
                  f"Expected: {r.expected_band:<10} Got: {r.actual_band}")

    print(f"\n  Summary: {passed}/{total} tests passed ({pass_rate:.0%})")
    print("=" * w)
    return pass_rate


def print_comparison(clip_results: list[TestResult],
                     fashion_results: list[TestResult]):
    """Print side-by-side comparison of CLIP vs FashionCLIP."""
    w = 90
    print("\n" + "=" * w)
    print("  SIDE-BY-SIDE COMPARISON: CLIP ViT-B/32 vs FashionCLIP")
    print("=" * w)
    print(f"  {'Test':<40} {'CLIP':>8} {'FashCLIP':>10} {'Winner':>8}")
    print("  " + "-" * (w - 2))

    clip_map = {r.test_name: r for r in clip_results}
    fash_map = {r.test_name: r for r in fashion_results}

    clip_wins = 0
    fashion_wins = 0
    ties = 0

    for name in clip_map:
        if name not in fash_map:
            continue
        cr = clip_map[name]
        fr = fash_map[name]

        # Determine who is closer to expected band
        c_ok = cr.passed
        f_ok = fr.passed
        if c_ok and not f_ok:
            winner = "CLIP"
            clip_wins += 1
        elif f_ok and not c_ok:
            winner = "Fashion"
            fashion_wins += 1
        elif c_ok == f_ok:
            winner = "Tie"
            ties += 1

        short = cr.description[:38]
        print(f"  {short:<40} {cr.score:>8.4f} {fr.score:>10.4f} {winner:>8}")

    print(f"\n  Wins: CLIP={clip_wins}  FashionCLIP={fashion_wins}  Ties={ties}")
    print("=" * w)


def print_verdict(clip_pass_rate: float, fashion_pass_rate: Optional[float]):
    """Print the final verdict and recommendation."""
    w = 78
    print("\n" + "=" * w)
    print("  FINAL VERDICT")
    print("=" * w)

    if clip_pass_rate >= 0.80:
        print(textwrap.dedent("""
    CLIP ViT-B/32 PASSES for GrailSeeker visual search.

    The model demonstrates sufficient ability to:
      - Distinguish between clothing categories
      - Recognize similar styles within categories
      - Separate clothing from non-clothing items

    Recommendation: Proceed with CLIP ViT-B/32 as the primary embedding model.
    Consider FashionCLIP for improved fashion-specific accuracy if available.
        """))
        verdict = "PASS"
    elif clip_pass_rate >= 0.60:
        print(textwrap.dedent("""
    CLIP ViT-B/32 is BORDERLINE for GrailSeeker visual search.

    The model shows moderate capability but misses some fashion distinctions.

    Recommendation: Consider switching to FashionCLIP
    (patrickjohncyh/fashion-clip) for better fashion-domain accuracy.
    Also consider fine-tuning on your specific second-hand clothing dataset.
        """))
        verdict = "BORDERLINE"
    else:
        print(textwrap.dedent("""
    CLIP ViT-B/32 FAILS for GrailSeeker visual search.

    The model does not reliably distinguish fashion items.

    Recommendation: Switch to FashionCLIP (patrickjohncyh/fashion-clip)
    or fine-tune CLIP on fashion-specific data. Consider also:
      - SigLIP (google/siglip-base-patch16-224)
      - FashionSAP or other fashion-specialized models
        """))
        verdict = "FAIL"

    if fashion_pass_rate is not None:
        if fashion_pass_rate > clip_pass_rate:
            delta = fashion_pass_rate - clip_pass_rate
            print(f"    FashionCLIP scored {delta:.0%} higher -- consider using it instead.")
        elif fashion_pass_rate < clip_pass_rate:
            print("    Surprisingly, vanilla CLIP outperformed FashionCLIP on these tests.")
            print("    This may be due to synthetic images; retest with real photos.")
        else:
            print("    CLIP and FashionCLIP performed equally on these tests.")

    print("=" * w)
    return verdict


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate CLIP quality for GrailSeeker fashion visual search"
    )
    parser.add_argument("--device", default="cpu",
                        help="Torch device: cpu, cuda, mps (default: cpu)")
    parser.add_argument("--include-fashion", action="store_true",
                        help="Also benchmark FashionCLIP (needs transformers)")
    parser.add_argument("--image-dir", type=str, default=None,
                        help="Path to directory with real test images")
    parser.add_argument("--save-synthetic", action="store_true",
                        help="Save generated synthetic images to disk for inspection")
    args = parser.parse_args()

    device = args.device
    if device == "mps" and not torch.backends.mps.is_available():
        print("  MPS not available, falling back to CPU")
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        print("  CUDA not available, falling back to CPU")
        device = "cpu"

    print(f"  Device: {device}")

    # ---- Generate / load images ----
    print("\n[1/5] Generating synthetic test images...")
    synth = generate_synthetic_images()
    print(f"  Created {len(synth)} synthetic images")

    real = download_real_images()
    disk = []
    if args.image_dir:
        print(f"\n  Loading images from {args.image_dir}...")
        disk = load_images_from_dir(args.image_dir)

    all_images = synth + real + disk
    image_map = {si.name: si for si in all_images}
    print(f"  Total test images: {len(all_images)}")

    if args.save_synthetic:
        out_dir = Path(__file__).parent / "synthetic_images"
        out_dir.mkdir(exist_ok=True)
        for si in synth:
            si.image.save(out_dir / f"{si.name}.png")
        print(f"  Saved synthetic images to {out_dir}")

    # ---- Load CLIP ----
    print("\n[2/5] Loading CLIP ViT-B/32 (open-clip-torch)...")
    clip_model, clip_preprocess, clip_tokenizer = load_clip_model(device)
    print("  CLIP loaded.")

    # ---- Embed images with CLIP ----
    print("\n[3/5] Embedding images with CLIP...")
    pil_images = [si.image for si in all_images]
    names = [si.name for si in all_images]
    clip_img_embs_arr = embed_images_clip(clip_model, clip_preprocess,
                                          pil_images, device)
    clip_img_embs = {name: clip_img_embs_arr[i]
                     for i, name in enumerate(names)}
    print(f"  Embedded {len(clip_img_embs)} images (dim={clip_img_embs_arr.shape[1]})")

    # ---- Embed text prompts ----
    text_prompts = list({tc.text_prompt for tc in TEXT_IMAGE_TESTS})
    clip_txt_embs_arr = embed_texts_clip(clip_model, clip_tokenizer,
                                         text_prompts, device)
    clip_txt_embs = {text: clip_txt_embs_arr[i]
                     for i, text in enumerate(text_prompts)}
    print(f"  Embedded {len(clip_txt_embs)} text prompts")

    # ---- Choose thresholds ----
    # Use relaxed thresholds for synthetic images, strict for real
    has_real = len(real) > 0 or len(disk) > 0
    thresholds = THRESHOLDS if has_real else SYNTHETIC_THRESHOLDS
    threshold_label = "standard" if has_real else "relaxed (synthetic images)"
    print(f"\n  Using {threshold_label} thresholds:")
    for band, (lo, hi) in thresholds.items():
        print(f"    {band:<10}: {lo:.2f} - {hi:.2f}")

    # ---- Run CLIP tests ----
    print("\n[4/5] Running similarity tests with CLIP...")
    clip_results = run_image_pair_tests(clip_img_embs, IMAGE_PAIR_TESTS,
                                        "CLIP ViT-B/32", thresholds)
    clip_results += run_text_image_tests(clip_img_embs, clip_txt_embs,
                                         TEXT_IMAGE_TESTS,
                                         "CLIP ViT-B/32", thresholds)
    clip_pass_rate = print_report(clip_results, "CLIP ViT-B/32")

    # ---- Optionally run FashionCLIP ----
    fashion_pass_rate = None
    fashion_results = []
    if args.include_fashion:
        print("\n[5/5] Loading and testing FashionCLIP...")
        fmodel, fprocessor = load_fashion_clip(device)
        if fmodel is not None:
            # Embed images
            fash_img_embs_arr = embed_images_fashion_clip(
                fmodel, fprocessor, pil_images, device)
            fash_img_embs = {name: fash_img_embs_arr[i]
                             for i, name in enumerate(names)}

            # Embed texts
            fash_txt_embs_arr = embed_texts_fashion_clip(
                fmodel, fprocessor, text_prompts, device)
            fash_txt_embs = {text: fash_txt_embs_arr[i]
                             for i, text in enumerate(text_prompts)}

            # Run tests
            fashion_results = run_image_pair_tests(
                fash_img_embs, IMAGE_PAIR_TESTS, "FashionCLIP", thresholds)
            fashion_results += run_text_image_tests(
                fash_img_embs, fash_txt_embs, TEXT_IMAGE_TESTS,
                "FashionCLIP", thresholds)
            fashion_pass_rate = print_report(fashion_results, "FashionCLIP")

            # Side-by-side
            print_comparison(clip_results, fashion_results)
    else:
        print("\n[5/5] Skipping FashionCLIP (use --include-fashion to enable)")

    # ---- Final verdict ----
    verdict = print_verdict(clip_pass_rate, fashion_pass_rate)

    # Exit code
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
