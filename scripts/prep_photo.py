#!/usr/bin/env python3
"""Remove a portrait background and prepare deterministic grayscale ASCII input."""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

try:
    from rembg import remove
except ImportError:
    remove = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a portrait for ASCII conversion")
    parser.add_argument("input", type=Path, help="Source portrait image")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("source-prepped.png"),
        help="Output grayscale PNG path",
    )
    return parser.parse_args()


def preprocess_image(input_path: Path, output_path: Path) -> None:
    if not input_path.is_file():
        raise FileNotFoundError(f"Input image not found: {input_path}")
    if remove is None:
        raise RuntimeError("rembg is unavailable; run: pip install -r scripts/requirements.txt")

    try:
        removed = remove(input_path.read_bytes())
        if isinstance(removed, Image.Image):
            rgba = removed.convert("RGBA")
        else:
            rgba = Image.open(io.BytesIO(removed)).convert("RGBA")
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"Could not process image {input_path}: {exc}") from exc

    pixels = np.asarray(rgba, dtype=np.uint8)
    rgb = pixels[:, :, :3]
    alpha = pixels[:, :, 3].astype(np.float32) / 255.0

    # Enhance only the isolated subject, then restore transparent pixels to pure white.
    grayscale = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    enhanced = clahe.apply(grayscale).astype(np.float32)
    composited = np.rint(enhanced * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(composited, mode="L").save(output_path, format="PNG", optimize=False, compress_level=9)
    print(f"Wrote {output_path}")


def main() -> None:
    args = parse_args()
    preprocess_image(args.input, args.output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from exc
