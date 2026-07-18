#!/usr/bin/env python3
"""Convert a preprocessed portrait into a self-contained animated ASCII SVG."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

RAMP = " .`:-=+*cs#%@"
FONT_FAMILY = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an animated monochrome ASCII portrait SVG")
    parser.add_argument("--input", "-i", type=Path, default=Path("source-prepped.png"))
    parser.add_argument("--output", "-o", type=Path, default=Path("ascii-portrait.svg"))
    parser.add_argument("--cols", type=int, default=100, help="ASCII columns")
    parser.add_argument("--rows", type=int, default=53, help="ASCII rows")
    parser.add_argument("--font-size", type=int, default=14)
    parser.add_argument("--title", default="Animated monochrome ASCII art of Arnav Prabhu's AP monogram")
    return parser.parse_args()


def brightness_to_glyph(value: int) -> str:
    index = round((255 - max(0, min(255, value))) / 255 * (len(RAMP) - 1))
    return RAMP[index]


def image_to_ascii_lines(image: Image.Image, cols: int, rows: int = 53) -> tuple[list[str], int]:
    """Downsample to a character grid whose 100×53 shape corrects glyph aspect ratio."""
    if cols <= 0 or rows <= 0:
        raise ValueError("Columns and rows must be positive")
    grayscale = image.convert("L")
    # White is the prepared background. Crop it before downsampling so the
    # subject uses the available ASCII grid instead of becoming a tiny island.
    subject_mask = grayscale.point(lambda value: 255 if value < 250 else 0)
    bounds = subject_mask.getbbox()
    if bounds is not None:
        left, top, right, bottom = bounds
        padding = max(2, round(max(right - left, bottom - top) * 0.06))
        bounds = (
            max(0, left - padding),
            max(0, top - padding),
            min(grayscale.width, right + padding),
            min(grayscale.height, bottom + padding),
        )
        grayscale = grayscale.crop(bounds)
    resized = grayscale.resize((cols, rows), Image.Resampling.LANCZOS)
    pixel_reader = getattr(resized, "get_flattened_data", resized.getdata)
    pixels = list(pixel_reader())
    lines = [
        "".join(brightness_to_glyph(value) for value in pixels[row * cols : (row + 1) * cols])
        for row in range(rows)
    ]
    return lines, rows


def build_svg(lines: list[str], font_size: int, title: str, static: bool = False) -> str:
    if not lines or not lines[0]:
        raise ValueError("ASCII grid is empty")

    columns = len(lines[0])
    char_width = font_size * 0.62
    line_height = font_size * 1.25
    pad_x, pad_y = 10, 10
    art_width = columns * char_width
    width = math.ceil(art_width + pad_x * 2)
    height = math.ceil(len(lines) * line_height + pad_y * 2)

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="portrait-title">'
        ),
        f'  <title id="portrait-title">{escape(title)}</title>',
        f'  <rect width="{width}" height="{height}" rx="12" fill="#0d1117"/>',
    ]

    if not static:
        out.append("  <defs>")
        for index in range(len(lines)):
            delay = 0.01 + index * 0.06
            out.extend(
                [
                    f'    <clipPath id="row-{index}-clip" clipPathUnits="userSpaceOnUse">',
                    f'      <rect x="0" y="{-font_size}" width="{art_width:.2f}" height="{line_height:.2f}">',
                    f'        <set attributeName="width" to="0" begin="0s" end="{delay:.2f}s"/>',
                    (
                        f'        <animate attributeName="width" from="0" to="{art_width:.2f}" '
                        f'begin="{delay:.2f}s" dur="0.75s" fill="freeze"/>'
                    ),
                    "      </rect>",
                    "    </clipPath>",
                ]
            )
        out.append("  </defs>")

    out.append(
        f'  <g font-family="{FONT_FAMILY}" font-size="{font_size}" fill="#b7bec7" xml:space="preserve">'
    )
    for index, row in enumerate(lines):
        baseline = pad_y + (index + 1) * line_height - (line_height - font_size) / 2
        delay = 0.01 + index * 0.06
        clip = "" if static else f' clip-path="url(#row-{index}-clip)"'
        out.append(f'    <g transform="translate({pad_x} {baseline:.2f})">')
        out.append(
            f'      <text x="0" y="0" textLength="{art_width:.2f}" lengthAdjust="spacingAndGlyphs"{clip}>{escape(row)}</text>'
        )
        if not static:
            cursor_end = max(0.0, art_width - 3)
            out.extend(
                [
                    f'      <rect x="0" y="{-font_size * 0.82:.2f}" width="3" height="{font_size:.2f}" fill="#d9dee5" opacity="0">',
                    (
                        f'        <animate attributeName="x" from="0" to="{cursor_end:.2f}" '
                        f'begin="{delay:.2f}s" dur="0.75s" fill="freeze"/>'
                    ),
                    (
                        f'        <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.02;0.90;1" '
                        f'begin="{delay:.2f}s" dur="0.75s" fill="freeze"/>'
                    ),
                    "      </rect>",
                ]
            )
        out.append("    </g>")
    out.extend(["  </g>", "</svg>"])
    return "\n".join(out) + "\n"


def main() -> None:
    args = parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(f"Input image not found: {args.input}")
    if args.font_size <= 0:
        raise ValueError("Font size must be positive")

    with Image.open(args.input) as image:
        lines, _ = image_to_ascii_lines(image, args.cols, args.rows)
    svg = build_svg(lines, args.font_size, args.title, static=os.environ.get("STATIC") == "1")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from exc
