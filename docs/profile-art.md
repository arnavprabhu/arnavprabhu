# Profile art implementation notes

## Contribution data schema

`scripts/fetch_contributions.py` writes `data/contributions.json` in this shape:

```json
{
  "username": "arnavprabhu",
  "generated_at": "ISO-8601 UTC timestamp",
  "period": {
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD"
  },
  "stats": {
    "total": 0,
    "current_streak": 0,
    "longest_streak": 0,
    "best_day": {"date": "YYYY-MM-DD", "count": 0},
    "monthly_totals": {"YYYY-MM": 0}
  },
  "days": [
    {
      "date": "YYYY-MM-DD",
      "count": 0,
      "level": 0,
      "weekday": 0,
      "week": 0
    }
  ]
}
```

`weekday` is Sunday-first (`0` through `6`). `week` is zero-based from the first date in the fetched calendar. GitHub contribution levels are clamped to the five supported values (`0` through `4`).

## Streak semantics

- A streak is a sequence of consecutive calendar days with at least one contribution.
- A zero-contribution day or a missing calendar date breaks the streak.
- The current streak ends on today, or on the latest available calendar date when the dataset ends earlier.
- The longest streak is calculated across the complete displayed period.

## Failure safety

The scraper validates that it received a contiguous calendar of roughly 53 weeks and resolved counts for positive-level days. It writes through a temporary file and atomically replaces the existing JSON only after validation, so an empty or malformed scrape cannot erase valid data.

## Rendering and fallback

All visual assets are self-contained SVGs. Their base SVG state is the readable final frame. SMIL `<set>` and `<animate>` elements temporarily hide and reveal content in supporting renderers; a renderer without SMIL support therefore displays the final frame rather than a blank panel. `STATIC=1` disables animation entirely for local previews.

The AP monogram is intentionally used as the ASCII source art, as selected for this profile.
