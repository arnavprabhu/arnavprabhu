#!/usr/bin/env python3
"""Generate a terminal/neofetch-style profile card as an animated SVG."""

from __future__ import annotations

import argparse
import os
import textwrap
from pathlib import Path
from typing import Sequence
from xml.sax.saxutils import escape

DEFAULT_USERNAME = os.environ.get("GITHUB_PROFILE_USERNAME", "arnavprabhu")
BASE_FIELDS: tuple[tuple[str, str], ...] = (
    ("Now", "Finance & Business Analytics student"),
    ("Building", "Uraion Labs · resilient AI systems"),
    ("Stack", "Python · FastAPI · SQL · Linux · GitHub Actions"),
    ("Focus", "ML systems · research · product analytics"),
    ("Highlights", "Research, models, and useful open-source tools"),
)
FONT_FAMILY = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an animated neofetch-style SVG info card")
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--output", "-o", type=Path, default=Path("info-card.svg"))
    parser.add_argument("--width", type=int, default=490)
    return parser.parse_args()


def _visual_lines(fields: Sequence[tuple[str, str]], max_value_chars: int = 39) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    for key, value in fields:
        wrapped = textwrap.wrap(
            value,
            width=max_value_chars,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        lines.extend((key if index == 0 else "", line) for index, line in enumerate(wrapped))
    return lines


def make_svg(
    width: int,
    static: bool = False,
    username: str = DEFAULT_USERNAME,
    fields: Sequence[tuple[str, str]] | None = None,
) -> str:
    if width < 360:
        raise ValueError("Info-card width must be at least 360px")

    pad_x, pad_y = 18, 18
    title_height = 48
    # 33px keeps the rendered card (~396px tall) aligned with the portrait at
    # README display widths: 490px card beside an 888×948 SVG shown at 370px.
    line_height = 33
    font_size = 14
    key_x = pad_x + 6
    value_x = pad_x + 112
    card_fields = (
        fields
        if fields is not None
        else (*BASE_FIELDS, ("Contact", f"{username}.com · uraionlabs.com"))
    )
    lines = _visual_lines(card_fields)
    first_line_y = pad_y + title_height + 35
    height = first_line_y + (len(lines) - 1) * line_height + 31

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="card-title">'
        ),
        f'  <title id="card-title">Terminal profile information for {escape(username)}</title>',
        f'  <rect width="{width}" height="{height}" rx="12" fill="#0d1117" stroke="#30363d"/>',
        f'  <rect x="{pad_x}" y="{pad_y}" width="{width - 2 * pad_x}" height="{title_height}" rx="8" fill="#161b22"/>',
    ]

    # Base state is the readable final frame. SMIL-capable renderers hide each
    # line with <set> until its reveal; non-SMIL renderers retain this fallback.
    out.append('  <g opacity="1">')
    if not static:
        out.extend(
            [
                '    <set attributeName="opacity" to="0" begin="0s" end="0.08s"/>',
                '    <animate attributeName="opacity" from="0" to="1" begin="0.08s" dur="0.32s" fill="freeze"/>',
                '    <animateTransform attributeName="transform" type="translate" from="8 0" to="0 0" begin="0.08s" dur="0.32s" fill="freeze"/>',
            ]
        )
    out.append(
        f'    <text x="{pad_x + 12}" y="{pad_y + 31}" font-family="{FONT_FAMILY}" font-size="18" font-weight="600" fill="#7ee787">{escape(username)}@github</text>'
    )
    out.append(
        f'    <rect x="{width - pad_x - 20}" y="{pad_y + 17}" width="8" height="14" fill="#58a6ff"/>'
    )
    out.append("  </g>")

    for index, (key, value) in enumerate(lines):
        y = first_line_y + index * line_height
        delay = 0.22 + index * 0.13
        out.append('  <g opacity="1">')
        if not static:
            out.extend(
                [
                    f'    <set attributeName="opacity" to="0" begin="0s" end="{delay:.2f}s"/>',
                    f'    <animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.34s" fill="freeze"/>',
                    f'    <animateTransform attributeName="transform" type="translate" from="8 0" to="0 0" begin="{delay:.2f}s" dur="0.34s" fill="freeze"/>',
                ]
            )
        if key:
            out.append(
                f'    <text x="{key_x}" y="{y}" font-family="{FONT_FAMILY}" font-size="{font_size}" font-weight="600" fill="#7ee787">{escape(key)}</text>'
            )
            out.append(
                f'    <text x="{value_x - 14}" y="{y}" font-family="{FONT_FAMILY}" font-size="{font_size}" fill="#8b949e">:</text>'
            )
        out.append(
            f'    <text x="{value_x}" y="{y}" font-family="{FONT_FAMILY}" font-size="{font_size}" fill="#c9d1d9">{escape(value)}</text>'
        )
        out.append("  </g>")

    out.extend(["</svg>"])
    return "\n".join(out) + "\n"


def main() -> None:
    args = parse_args()
    svg = make_svg(
        args.width,
        static=os.environ.get("STATIC") == "1",
        username=args.username,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from exc
