#!/usr/bin/env bash
set -euo pipefail

health_file="${1:-health/latest.json}"
output_dir="badges"

if ! command -v jq >/dev/null 2>&1; then
  printf 'jq is required\n' >&2
  exit 1
fi

if [[ ! -r "$health_file" ]]; then
  printf 'Cannot read health summary: %s\n' "$health_file" >&2
  exit 1
fi

if ! jq -e '._trust_summary.by_status | type == "object"' "$health_file" >/dev/null 2>&1; then
  printf 'Invalid trust summary: %s\n' "$health_file" >&2
  exit 1
fi

mkdir -p "$output_dir"

while IFS=$'\t' read -r status count color; do
  badge_file="${output_dir}/status-${status}.svg"

  if (( count == 0 )); then
    rm -f "$badge_file"
    continue
  fi

  label="${status}: ${count}"
  escaped_label="$(jq -rn --arg value "$label" '$value | @html')"

  printf '%s\n' \
    '<svg xmlns="http://www.w3.org/2000/svg" width="110" height="20" role="img" aria-label="health: '"$escaped_label"'">' \
    '  <title>health: '"$escaped_label"'</title>' \
    '  <clipPath id="r"><rect width="110" height="20" rx="3" fill="#fff"/></clipPath>' \
    '  <g clip-path="url(#r)">' \
    '    <rect width="35" height="20" fill="#555"/>' \
    '    <rect x="35" width="75" height="20" fill="'"$color"'"/>' \
    '  </g>' \
    '  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="9">' \
    '    <text x="17.5" y="14">health</text>' \
    '    <text x="72.5" y="14" textLength="68" lengthAdjust="spacingAndGlyphs">'"$escaped_label"'</text>' \
    '  </g>' \
    '</svg>' > "$badge_file"
done < <(jq -r '
  ._trust_summary.by_status as $counts
  | [
      ["fresh", ($counts.fresh // 0), "#4c1"],
      ["aging", ($counts.aging // 0), "#dfb317"],
      ["stale", ($counts.stale // 0), "#fe7d37"],
      ["degraded", ($counts.degraded // 0), "#e05d44"],
      ["browser-dependent", ($counts.browser_dependent // 0), "#007ec6"],
      ["unreachable", ($counts.unreachable // 0), "#e05d44"],
      ["unknown", ($counts.unknown // 0), "#9f9f9f"],
      ["unknown-freshness", ($counts.unknown_freshness // 0), "#9f7aea"]
    ][]
  | select(.[1] | type == "number" and . >= 0 and floor == .)
  | @tsv
' "$health_file")
