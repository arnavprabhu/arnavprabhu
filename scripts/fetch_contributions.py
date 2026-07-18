#!/usr/bin/env python3
"""Fetch GitHub's public contribution calendar without an API token."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

DEFAULT_USERNAME = os.environ.get("GITHUB_PROFILE_USERNAME", "arnavprabhu")
USER_AGENT = "arnavprabhu-profile-readme/1.0 (+https://github.com/arnavprabhu/arnavprabhu)"
COUNT_RE = re.compile(r"([0-9][0-9,]*)\s+contribution", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a public GitHub contribution calendar")
    parser.add_argument("--username", "-u", default=DEFAULT_USERNAME, help="GitHub username")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/contributions.json"),
        help="Output JSON path",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    return parser.parse_args()


def fetch_page(username: str, timeout: float = 20.0) -> str:
    if not username or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        raise ValueError(f"Invalid GitHub username: {username!r}")

    response = requests.get(
        f"https://github.com/users/{username}/contributions",
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def _count_from_text(text: str | None) -> int | None:
    if not text:
        return None
    if re.search(r"\bno contributions?\b", text, re.IGNORECASE):
        return 0
    match = COUNT_RE.search(text)
    return int(match.group(1).replace(",", "")) if match else None


def _extract_count(cell: Tag, soup: BeautifulSoup, level: int) -> int:
    for attribute in ("data-count", "data-contribution-count"):
        raw = cell.get(attribute)
        if raw is not None:
            try:
                return max(0, int(str(raw).replace(",", "")))
            except ValueError:
                pass

    candidates: list[str] = []
    for attribute in ("aria-label", "title"):
        raw = cell.get(attribute)
        if isinstance(raw, str):
            candidates.append(raw)

    cell_id = cell.get("id")
    if isinstance(cell_id, str):
        tooltip = soup.find("tool-tip", attrs={"for": cell_id})
        if isinstance(tooltip, Tag):
            candidates.append(tooltip.get_text(" ", strip=True))

    sibling = cell.find_next_sibling("tool-tip")
    if isinstance(sibling, Tag):
        candidates.append(sibling.get_text(" ", strip=True))

    for candidate in candidates:
        count = _count_from_text(candidate)
        if count is not None:
            return count

    if level == 0:
        return 0
    raise ValueError(f"Could not determine contribution count for {cell.get('data-date')}")


def parse_days(html: str) -> list[dict[str, Any]]:
    """Parse semantic contribution cells and return date-sorted day records."""
    soup = BeautifulSoup(html, "html.parser")
    cells = soup.select("[data-date][data-level]")

    by_date: dict[str, dict[str, Any]] = {}
    for cell in cells:
        if not isinstance(cell, Tag):
            continue
        raw_date = cell.get("data-date")
        if not isinstance(raw_date, str):
            continue
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValueError(f"Invalid contribution date: {raw_date!r}") from exc

        try:
            level = max(0, int(str(cell.get("data-level", "0"))))
        except ValueError:
            level = 0

        by_date[raw_date] = {
            "date": raw_date,
            "count": _extract_count(cell, soup, level),
            "level": level,
            "_date": parsed_date,
        }

    records = sorted(by_date.values(), key=lambda item: item["_date"])
    if not records:
        return []

    first_date = records[0]["_date"]
    days: list[dict[str, Any]] = []
    for record in records:
        parsed_date = record.pop("_date")
        record["weekday"] = (parsed_date.weekday() + 1) % 7  # Sunday = 0.
        record["week"] = (parsed_date - first_date).days // 7
        days.append(record)
    return days


def validate_days(days: list[dict[str, Any]]) -> None:
    if not days:
        raise ValueError("No contribution cells were found; GitHub's markup may have changed")
    if not 350 <= len(days) <= 380:
        raise ValueError(f"Expected roughly 53 weeks of data, found {len(days)} days")

    parsed_dates = [date.fromisoformat(str(item["date"])) for item in days]
    if len(set(parsed_dates)) != len(parsed_dates):
        raise ValueError("Duplicate contribution dates were found")
    if parsed_dates != sorted(parsed_dates):
        raise ValueError("Contribution dates are not sorted")
    if (parsed_dates[-1] - parsed_dates[0]).days + 1 != len(parsed_dates):
        raise ValueError("Contribution calendar contains missing dates")
    if any(int(item["count"]) < 0 for item in days):
        raise ValueError("Contribution counts cannot be negative")


def compute_stats(days: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    if not days:
        return {
            "total": 0,
            "current_streak": 0,
            "longest_streak": 0,
            "best_day": None,
            "monthly_totals": {},
        }

    parsed = sorted(
        ((date.fromisoformat(str(item["date"])), int(item.get("count", 0))) for item in days),
        key=lambda item: item[0],
    )
    count_by_date = {day: count for day, count in parsed}
    first_date, last_date = parsed[0][0], parsed[-1][0]

    streak_end = min(today or date.today(), last_date)
    current_streak = 0
    if streak_end >= first_date:
        probe = streak_end
        while count_by_date.get(probe, 0) > 0:
            current_streak += 1
            probe -= timedelta(days=1)

    longest_streak = 0
    run = 0
    previous_date: date | None = None
    previous_count = 0
    for day, count in parsed:
        consecutive = previous_date is not None and day == previous_date + timedelta(days=1)
        if count > 0:
            run = run + 1 if consecutive and previous_count > 0 else 1
            longest_streak = max(longest_streak, run)
        else:
            run = 0
        previous_date, previous_count = day, count

    best_date, best_count = max(parsed, key=lambda item: (item[1], -item[0].toordinal()))
    monthly_totals: dict[str, int] = {}
    for day, count in parsed:
        month = day.strftime("%Y-%m")
        monthly_totals[month] = monthly_totals.get(month, 0) + count

    return {
        "total": sum(count for _, count in parsed),
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "best_day": {"date": best_date.isoformat(), "count": best_count},
        "monthly_totals": monthly_totals,
    }


def build_payload(username: str, days: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "username": username,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "period": {"start": days[0]["date"], "end": days[-1]["date"]},
        "stats": compute_stats(days),
        "days": days,
    }


def write_payload(payload: dict[str, Any], output: Path) -> None:
    """Atomically replace output only after a complete, valid payload exists."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)


def main() -> None:
    args = parse_args()
    days = parse_days(fetch_page(args.username, timeout=args.timeout))
    validate_days(days)
    payload = build_payload(args.username, days)
    write_payload(payload, args.output)
    stats = payload["stats"]
    print(f"Wrote {args.output}")
    print(
        f"days={len(days)} total={stats['total']} "
        f"current_streak={stats['current_streak']} longest={stats['longest_streak']}"
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, requests.RequestException) as exc:
        raise SystemExit(f"error: {exc}") from exc
