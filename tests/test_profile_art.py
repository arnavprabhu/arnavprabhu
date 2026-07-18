from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import scripts.fetch_contributions as contributions
from scripts.fetch_contributions import compute_stats, parse_days
from scripts.make_ascii_svg import build_svg as make_ascii_svg
from scripts.make_ascii_svg import image_to_ascii_lines
from scripts.make_info_card import make_svg as make_info_svg
from scripts.render_heatmap_svg import PALETTE


ROOT = Path(__file__).resolve().parents[1]


class ContributionTests(unittest.TestCase):
    def test_semantic_cells_include_counts_and_calendar_coordinates(self) -> None:
        html = """
        <table><tbody><tr>
          <td id="day-a" data-date="2026-07-12" data-level="0"></td>
          <tool-tip for="day-a">No contributions on July 12th.</tool-tip>
          <td id="day-b" data-date="2026-07-13" data-level="2" data-count="3"></td>
          <td id="day-c" data-date="2026-07-14" data-level="4" aria-label="12 contributions on July 14th"></td>
        </tr></tbody></table>
        """
        days = parse_days(html)
        self.assertEqual([d["count"] for d in days], [0, 3, 12])
        self.assertEqual(days[0]["weekday"], 0)  # Sunday-first, like GitHub.
        self.assertEqual(days[1]["weekday"], 1)
        self.assertEqual([d["week"] for d in days], [0, 0, 0])

    def test_stats_match_documented_schema_and_streak_definition(self) -> None:
        days = [
            {"date": "2026-07-12", "count": 1, "level": 1, "weekday": 0, "week": 0},
            {"date": "2026-07-13", "count": 2, "level": 2, "weekday": 1, "week": 0},
            {"date": "2026-07-14", "count": 0, "level": 0, "weekday": 2, "week": 0},
            {"date": "2026-07-15", "count": 5, "level": 4, "weekday": 3, "week": 0},
            {"date": "2026-07-16", "count": 1, "level": 1, "weekday": 4, "week": 0},
        ]
        stats = compute_stats(days, today=date(2026, 7, 16))
        self.assertEqual(stats["total"], 9)
        self.assertEqual(stats["current_streak"], 2)
        self.assertEqual(stats["longest_streak"], 2)
        self.assertEqual(stats["best_day"], {"date": "2026-07-15", "count": 5})
        self.assertEqual(stats["monthly_totals"], {"2026-07": 9})

    def test_empty_scrape_cannot_overwrite_existing_valid_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "contributions.json"
            output.write_text('{"valid": true}\n', encoding="utf-8")
            argv = ["fetch_contributions.py", "--output", str(output)]
            with patch.object(contributions, "fetch_page", return_value="<html></html>"), patch.object(
                sys, "argv", argv
            ):
                with self.assertRaises(ValueError):
                    contributions.main()
            self.assertEqual(output.read_text(encoding="utf-8"), '{"valid": true}\n')


class SvgGeneratorTests(unittest.TestCase):
    def test_ascii_defaults_to_approximately_100_by_53(self) -> None:
        image = Image.new("L", (400, 400), 255)
        lines, rows = image_to_ascii_lines(image, cols=100)
        self.assertEqual(rows, 53)
        self.assertEqual(len(lines), 53)
        self.assertTrue(all(len(line) == 100 for line in lines))
        self.assertTrue(all(set(line) <= {" "} for line in lines))

    def test_ascii_crops_large_white_margin_around_subject(self) -> None:
        image = Image.new("L", (200, 200), color=255)
        for x in range(75, 125):
            for y in range(75, 125):
                image.putpixel((x, y), 0)
        lines, _ = image_to_ascii_lines(image, 100, 53)
        dense_glyphs = sum(character != " " for line in lines for character in line)
        self.assertGreater(dense_glyphs, 3_500)

    def test_info_card_static_mode_has_final_state_and_correct_identity(self) -> None:
        svg = make_info_svg(490, static=True, username="arnavprabhu")
        ET.fromstring(svg)
        self.assertIn("arnavprabhu@github", svg)
        self.assertNotIn("<animate", svg)
        self.assertNotIn("Less → More", svg)

    def test_animated_assets_keep_a_readable_non_smil_final_frame(self) -> None:
        ascii_svg = make_ascii_svg(["@" * 10], 14, "AP monogram", static=False)
        info_svg = make_info_svg(490, static=False, username="arnavprabhu")
        self.assertIn('fill="#0d1117"', ascii_svg)
        self.assertIn('<set attributeName="width" to="0"', ascii_svg)
        self.assertIn('<g opacity="1">', info_svg)
        self.assertIn('<set attributeName="opacity" to="0"', info_svg)

    def test_palette_matches_github_levels_zero_through_four(self) -> None:
        self.assertEqual(len(PALETTE), 5)

    def test_write_enabled_workflow_actions_are_sha_pinned(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "update-profile-art.yml").read_text()
        uses = [line.split("@", 1)[1].split()[0] for line in workflow.splitlines() if "uses:" in line]
        self.assertTrue(uses)
        self.assertTrue(all(len(reference) == 40 for reference in uses))
        self.assertTrue(all(all(character in "0123456789abcdef" for character in reference) for reference in uses))

    def test_build_helper_accepts_python_as_second_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "calls.log"
            fake_python = Path(tmp) / "fake-python"
            fake_python.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\n')
            fake_python.chmod(0o755)
            subprocess.run(
                [str(ROOT / "scripts" / "build_terminal_profile.sh"), "different-user", str(fake_python)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            calls = log.read_text().splitlines()
            self.assertEqual(len(calls), 5)
            self.assertTrue(any("--username different-user" in call for call in calls))

    def test_full_cli_outputs_are_valid_self_contained_svg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = {
                "username": "arnavprabhu",
                "generated_at": "2026-07-18T00:00:00Z",
                "period": {"start": "2026-07-12", "end": "2026-07-18"},
                "stats": {
                    "total": 9,
                    "current_streak": 2,
                    "longest_streak": 4,
                    "best_day": {"date": "2026-07-15", "count": 5},
                    "monthly_totals": {"2026-07": 9},
                },
                "days": [
                    {
                        "date": f"2026-07-{day:02d}",
                        "count": 1 if day in (12, 13, 17, 18) else 0,
                        "level": 1 if day in (12, 13, 17, 18) else 0,
                        "weekday": index,
                        "week": 0,
                    }
                    for index, day in enumerate(range(12, 19))
                ],
            }
            data_path = tmp_path / "contributions.json"
            svg_path = tmp_path / "contribution-heatmap.svg"
            data_path.write_text(json.dumps(fixture), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_heatmap_svg.py"),
                    "--input",
                    str(data_path),
                    "--output",
                    str(svg_path),
                ],
                cwd=ROOT,
                check=True,
            )
            svg = svg_path.read_text(encoding="utf-8")
            root = ET.fromstring(svg)
            self.assertIn("viewBox", root.attrib)
            self.assertIn("9 contributions · 2-day streak · longest 4 days", svg)
            self.assertIn("<title>", svg)
            self.assertIn('fill="freeze"', svg)
            self.assertIn('<set attributeName="opacity" to="0"', svg)
            self.assertNotIn("repeatCount", svg)
            self.assertNotIn("<script", svg.lower())
            self.assertNotIn("stylesheet", svg.lower())


if __name__ == "__main__":
    unittest.main()
