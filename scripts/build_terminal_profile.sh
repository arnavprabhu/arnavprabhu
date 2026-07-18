#!/usr/bin/env bash
set -euo pipefail

USERNAME="${1:-${GITHUB_PROFILE_USERNAME:-arnavprabhu}}"
PYTHON="${2:-${PYTHON:-python3}}"

printf 'Generating profile art for @%s\n' "$USERNAME"
"$PYTHON" scripts/prep_photo.py source-photo.jpg --output source-prepped.png
"$PYTHON" scripts/make_ascii_svg.py --input source-prepped.png --output ascii-portrait.svg --cols 100 --rows 53
"$PYTHON" scripts/make_info_card.py --username "$USERNAME" --output info-card.svg
"$PYTHON" scripts/fetch_contributions.py --username "$USERNAME" --output data/contributions.json
"$PYTHON" scripts/render_heatmap_svg.py --input data/contributions.json --output contribution-heatmap.svg --width 860
printf 'Generated ascii-portrait.svg, info-card.svg, and contribution-heatmap.svg\n'
