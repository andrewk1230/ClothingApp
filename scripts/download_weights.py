"""
Download YOLOv8 DeepFashion2 pretrained weights from HuggingFace.

Usage:
    python scripts/download_weights.py

Downloads the Bingsu/adetailer deepfashion2_yolov8s-seg model to
backend/app/ml/weights/deepfashion2_yolov8s-seg.pt
"""

import os
import sys
from pathlib import Path

WEIGHTS_URL = "https://huggingface.co/Bingsu/adetailer/resolve/main/deepfashion2_yolov8s-seg.pt"
WEIGHTS_DIR = Path(__file__).parent.parent / "backend" / "app" / "ml" / "weights"
WEIGHTS_FILE = WEIGHTS_DIR / "deepfashion2_yolov8s-seg.pt"


def main():
    if WEIGHTS_FILE.exists():
        print(f"Weights already exist at {WEIGHTS_FILE}")
        return

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import httpx
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
        import httpx

    print(f"Downloading DeepFashion2 YOLOv8s-seg weights from HuggingFace...")
    print(f"URL: {WEIGHTS_URL}")

    tmp_file = WEIGHTS_FILE.with_suffix(WEIGHTS_FILE.suffix + ".tmp")
    try:
        with httpx.stream("GET", WEIGHTS_URL, follow_redirects=True, timeout=120.0) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(tmp_file, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r  {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB ({pct:.0f}%)", end="", flush=True)

        os.replace(tmp_file, WEIGHTS_FILE)
    except BaseException:
        tmp_file.unlink(missing_ok=True)
        raise

    print(f"\nSaved to {WEIGHTS_FILE}")
    print(f"File size: {WEIGHTS_FILE.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
