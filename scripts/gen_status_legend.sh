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

  label="${status}: ${count}"
  escaped_label="$(jq -rn --arg value "$label" '$value | @html')"
  stroke_dasharray=""
  if [[ "$status" == "unknown-freshness" ]]; then
    stroke_dasharray=' stroke-dasharray="2,2"'
  fi

  printf '%s\n' \
    '<svg xmlns="http://www.w3.org/2000/svg" width="110" height="20" role="img" aria-label="health: '"$escaped_label"'">' \
    '  <title>health: '"$escaped_label"'</title>' \
    '  <rect x="0.5" y="0.5" width="109" height="19" rx="3" fill="#0d1117" stroke="'"$color"'" stroke-width="1"'"$stroke_dasharray"'/>' \
    '  <g fill="'"$color"'" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="10" font-weight="500">' \
    '    <text x="17.5" y="14">health</text>' \
    '    <text x="72.5" y="14" textLength="68" lengthAdjust="spacingAndGlyphs">'"$escaped_label"'</text>' \
    '  </g>' \
    '</svg>' > "$badge_file"
done < <(jq -r '
  ._trust_summary.by_status as $counts
  | [
      ["fresh", ($counts.fresh // 0), "#3fb950"],
      ["aging", ($counts.aging // 0), "#d29922"],
      ["stale", ($counts.stale // 0), "#f85149"],
      ["degraded", ($counts.degraded // 0), "#a371f7"],
      ["browser-dependent", ($counts.browser_dependent // 0), "#58a6ff"],
      ["unreachable", ($counts.unreachable // 0), "#f85149"],
      ["unknown", ($counts.unknown // 0), "#6e7681"],
      ["unknown-freshness", ($counts.unknown_freshness // 0), "#6e7681"]
    ][]
  | select(.[1] | type == "number" and . >= 0 and floor == .)
  | @tsv
' "$health_file")
