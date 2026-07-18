#!/usr/bin/env python3
"""Render contribution JSON as a self-contained animated 53-week SVG."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

PALETTE = [
    "#161b22",
    "#0e4429",
    "#006d32",
    "#26a641",
    "#39d353",
]
FONT_FAMILY = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an animated GitHub contribution heatmap")
    parser.add_argument("--input", "-i", type=Path, default=Path("data/contributions.json"))
    parser.add_argument("--output", "-o", type=Path, default=Path("contribution-heatmap.svg"))
    parser.add_argument("--width", type=int, default=860)
    parser.add_argument("--cell", type=int, default=12)
    parser.add_argument("--gap", type=int, default=4)
    return parser.parse_args()


def calendar_cells(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return 53 Sunday-to-Saturday columns ending in the latest day's week."""
    if not days:
        raise ValueError("Contribution JSON contains no days")

    by_date: dict[date, dict[str, Any]] = {}
    for item in days:
        parsed_date = date.fromisoformat(str(item["date"]))
        by_date[parsed_date] = item

    latest = max(by_date)
    latest_weekday = (latest.weekday() + 1) % 7
    end_saturday = latest + timedelta(days=6 - latest_weekday)
    start_sunday = end_saturday - timedelta(days=53 * 7 - 1)

    cells: list[dict[str, Any]] = []
    for offset in range(53 * 7):
        cell_date = start_sunday + timedelta(days=offset)
        source = by_date.get(cell_date)
        if source is None or cell_date > latest:
            cells.append({"date": "", "count": 0, "level": 0, "empty": True})
        else:
            cells.append(
                {
                    "date": cell_date.isoformat(),
                    "count": max(0, int(source.get("count", 0))),
                    "level": max(0, int(source.get("level", 0))),
                    "empty": False,
                }
            )
    return cells


def make_svg(payload: dict[str, Any], args: argparse.Namespace, static: bool = False) -> str:
    width = args.width
    cell = args.cell
    gap = args.gap
    if width <= 0 or cell <= 0 or gap < 0:
        raise ValueError("Width and cell must be positive; gap cannot be negative")

    rows, columns = 7, 53
    margin_x = 14
    advance = cell + gap
    grid_width = columns * cell + (columns - 1) * gap
    if margin_x + grid_width > width:
        raise ValueError(
            f"Heatmap needs at least {margin_x + grid_width}px but configured width is {width}px"
        )

    title_y = 23
    period_y = 41
    grid_y = 57
    grid_height = rows * cell + (rows - 1) * gap
    legend_y = grid_y + grid_height + 22
    footer_y = legend_y + 24
    height = footer_y + 14

    username = str(payload.get("username", "github"))
    period = payload.get("period", {})
    stats = payload.get("stats", {})
    total = int(stats.get("total", 0))
    current = int(stats.get("current_streak", 0))
    longest = int(stats.get("longest_streak", 0))
    cells = calendar_cells(payload.get("days", []))

    period_text = f"{period.get('start', '')} → {period.get('end', '')}"
    footer_text = (
        f"{total:,} contributions · {current}-day streak · "
        f"longest {longest} {'day' if longest == 1 else 'days'}"
    )
    accessible_title = (
        f"{username} GitHub contribution heatmap: {footer_text}, "
        f"from {period.get('start', '')} to {period.get('end', '')}."
    )

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="heatmap-title">'
        ),
        f'  <title id="heatmap-title">{escape(accessible_title)}</title>',
        f'  <rect width="{width}" height="{height}" rx="10" fill="#0d1117"/>',
        (
            f'  <text x="{margin_x}" y="{title_y}" font-family="{FONT_FAMILY}" '
            f'font-size="16" font-weight="600" fill="#c9d1d9">{escape(username)}@github · contributions</text>'
        ),
        (
            f'  <text x="{margin_x}" y="{period_y}" font-family="{FONT_FAMILY}" '
            f'font-size="12" fill="#8b949e">{escape(period_text)}</text>'
        ),
    ]

    for index, item in enumerate(cells):
        week = index // rows
        weekday = index % rows
        x = margin_x + week * advance
        final_y = grid_y + weekday * advance
        level = min(max(int(item.get("level", 0)), 0), len(PALETTE) - 1)
        color = PALETTE[level]
        date_value = str(item.get("date", ""))
        count = int(item.get("count", 0))
        label = f"{date_value}: {count} contributions" if date_value else "Outside displayed contribution period"

        if static:
            out.append(
                f'  <rect x="{x}" y="{final_y}" width="{cell}" height="{cell}" rx="2" '
                f'fill="{color}" opacity="1" data-date="{escape(date_value)}"><title>{escape(label)}</title></rect>'
            )
            continue

        delay = 0.01 + week * 0.024 + weekday * 0.045
        start_y = final_y - 6
        out.extend(
            [
                (
                    f'  <rect x="{x}" y="{final_y}" width="{cell}" height="{cell}" rx="2" '
                    f'fill="{color}" opacity="1" data-date="{escape(date_value)}">'
                ),
                f'    <title>{escape(label)}</title>',
                f'    <set attributeName="opacity" to="0" begin="0s" end="{delay:.3f}s"/>',
                (
                    f'    <animate attributeName="y" from="{start_y}" to="{final_y}" '
                    f'begin="{delay:.3f}s" dur="0.38s" fill="freeze"/>'
                ),
                (
                    f'    <animate attributeName="opacity" from="0" to="1" '
                    f'begin="{delay:.3f}s" dur="0.26s" fill="freeze"/>'
                ),
                "  </rect>",
            ]
        )

    out.append(
        f'  <text x="{margin_x}" y="{legend_y}" font-family="{FONT_FAMILY}" font-size="12" fill="#8b949e">Less</text>'
    )
    legend_x = margin_x + 34
    for index, color in enumerate(PALETTE):
        x = legend_x + index * (cell + 4)
        out.append(f'  <rect x="{x}" y="{legend_y - cell + 2}" width="{cell}" height="{cell}" rx="2" fill="{color}"/>')
    more_x = legend_x + len(PALETTE) * (cell + 4) + 2
    out.append(
        f'  <text x="{more_x}" y="{legend_y}" font-family="{FONT_FAMILY}" font-size="12" fill="#8b949e">More</text>'
    )

    out.append(
        f'  <text x="{margin_x}" y="{footer_y}" font-family="{FONT_FAMILY}" font-size="13" fill="#8b949e" opacity="1">{escape(footer_text)}'
    )
    if not static:
        out.append('    <set attributeName="opacity" to="0" begin="0s" end="2.00s"/>')
        out.append('    <animate attributeName="opacity" from="0" to="1" begin="2.00s" dur="0.25s" fill="freeze"/>')
    out.extend(["  </text>", "</svg>"])
    return "\n".join(out) + "\n"


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    svg = make_svg(payload, args, static=os.environ.get("STATIC") == "1")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
