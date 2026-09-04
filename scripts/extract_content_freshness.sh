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
content_date_field="$(jq -r --arg id "$dataset_id" \
  '.datasets[$id].freshness["content-date-field"] // empty' "$probe_policy")"
content_format="$(jq -r --arg id "$dataset_id" \
  '.datasets[$id].format // empty' "$probe_policy")"

content_file="${DATAPULSE_CONTENT_FILE:-}"
temporary_file=""
if [[ -z "$content_file" ]]; then
  temporary_file="$(mktemp)"
  content_file="$temporary_file"
  trap 'rm -f "$temporary_file"' EXIT
  curl --location --silent --show-error --fail --max-time "${DATAPULSE_CURL_TIMEOUT:-30}" \
    --output "$content_file" "$url"
fi

case "${url%%\?*}" in
  *.parquet) parquet_input=1 ;;
  *) parquet_input=0 ;;
esac
if [[ "$content_file" == *.parquet || "$content_format" == "parquet" ]]; then
  parquet_input=1
fi

if [[ "$parquet_input" -eq 1 ]]; then
  python3 - "$content_file" "$extraction_mode" "$content_date_field" <<'PY'
from datetime import date, datetime
from pathlib import Path
import sys

try:
    import pyarrow.parquet as pq
except ImportError as error:
    raise SystemExit(
        "Parquet freshness extraction requires pyarrow; install requirements.txt"
    ) from error

path = Path(sys.argv[1])
extraction_mode = sys.argv[2]
date_field = sys.argv[3]
if not date_field:
    raise SystemExit("Parquet freshness extraction requires content-date-field")

table = pq.read_table(path)
if date_field not in table.column_names:
    raise SystemExit(
        f"Parquet freshness extraction field {date_field!r} is not a table column"
    )

dates: set[date] = set()
for value in table.column(date_field).to_pylist():
    if isinstance(value, datetime):
        dates.add(value.date())
    elif isinstance(value, date):
        dates.add(value)
    elif isinstance(value, str):
        try:
            dates.add(date.fromisoformat(value[:10]))
        except ValueError:
            pass

if dates:
    today = date.today()
    if extraction_mode == "min":
        print(min(dates).isoformat())
    else:
        past = {value for value in dates if value <= today}
        print(max(past).isoformat() if past else max(dates).isoformat())
PY
  exit 0
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
    today = date.today()
    # Rolling forecasts use the configured start (min date), not a future horizon.
    # When extraction-mode is "max", future dates (beyond today) are skipped so
    # the extraction surfaces the latest actual publication date instead of the
    # furthest forecast day. Mirrors check.sh's extract_max_date future-filter
    # so both code paths agree on the freshness signal.
    if extraction_mode == "min":
        print(min(dates).isoformat())
    else:
        past = {d for d in dates if d <= today}
        print(max(past).isoformat() if past else max(dates).isoformat())
PY
