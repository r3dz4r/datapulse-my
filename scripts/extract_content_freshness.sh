#!/usr/bin/env bash

set -euo pipefail

url="${1:?usage: extract_content_freshness.sh <url> <dataset_id>}"
dataset_id="${2:?usage: extract_content_freshness.sh <url> <dataset_id>}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
probe_policy="${DATAPULSE_PROBE_POLICY:-$script_dir/probe-policy.json}"
extraction_mode="$(jq -er --arg id "$dataset_id" \
  '.datasets[$id].freshness["extraction-mode"] // empty' "$probe_policy")" || {
  printf 'Probe policy error: %s requires a freshness extraction mode\n' "$dataset_id" >&2
  exit 1
}

content_file="${DATAPULSE_CONTENT_FILE:-}"
temporary_file=""
if [[ -z "$content_file" ]]; then
  temporary_file="$(mktemp)"
  content_file="$temporary_file"
  trap 'rm -f "$temporary_file"' EXIT
  curl --location --silent --show-error --fail --max-time "${DATAPULSE_CURL_TIMEOUT:-30}" \
    --output "$content_file" "$url"
fi

python3 - "$content_file" "$extraction_mode" <<'PY'
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
extraction_mode = sys.argv[2]
dates: set[date] = set()

try:
    payload = json.loads(text)
except json.JSONDecodeError:
    payload = None

if isinstance(payload, list):
    for row in payload:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str):
            continue
        try:
            dates.add(date.fromisoformat(row["date"][:10]))
        except ValueError:
            pass

for match in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", text):
    try:
        dates.add(date(*(int(part) for part in match.groups())))
    except ValueError:
        pass

months = {
    "jan": 1, "january": 1, "januari": 1,
    "feb": 2, "february": 2, "februari": 2,
    "mar": 3, "march": 3, "mac": 3,
    "apr": 4, "april": 4,
    "may": 5, "mei": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7, "julai": 7,
    "aug": 8, "august": 8, "ogos": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "oktober": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12, "disember": 12,
}
month_names = "|".join(sorted(months, key=len, reverse=True))
day_first = re.compile(
    rf"(?<!\d)(\d{{1,2}})\s+({month_names})\s+(\d{{4}})(?!\d)", re.IGNORECASE
)
month_first = re.compile(
    rf"\b({month_names})\s+(\d{{1,2}}),?\s+(\d{{4}})(?!\d)", re.IGNORECASE
)

for match in day_first.finditer(text):
    day, month_name, year = match.groups()
    try:
        dates.add(date(int(year), months[month_name.casefold()], int(day)))
    except ValueError:
        pass

for match in month_first.finditer(text):
    month_name, day, year = match.groups()
    try:
        dates.add(date(int(year), months[month_name.casefold()], int(day)))
    except ValueError:
        pass

if dates:
    # Rolling forecasts use the configured start (min date), not a future horizon.
    # Default: max date in the body IS the publication-freshness signal.
    if extraction_mode == "min":
        print(min(dates).isoformat())
    else:
        print(max(dates).isoformat())
PY
