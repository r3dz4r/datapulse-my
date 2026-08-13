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
    '  <rect x="0.5" y="0.5" width="109" height="19" rx="3" fill="#FFFFFF" stroke="'"$color"'" stroke-width="1"'"$stroke_dasharray"'/>' \
    '  <g fill="#0F172A" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="10" font-weight="500">' \
    '    <text x="17.5" y="14">health</text>' \
    '    <text x="72.5" y="14" textLength="68" lengthAdjust="spacingAndGlyphs">'"$escaped_label"'</text>' \
    '  </g>' \
    '</svg>' > "$badge_file"
done < <(jq -r '
  ._trust_summary.by_status as $counts
  | [
      ["fresh", ($counts.fresh // 0), "#16A34A"],
      ["aging", ($counts.aging // 0), "#CA8A04"],
      ["stale", ($counts.stale // 0), "#DC2626"],
      ["degraded", ($counts.degraded // 0), "#DC2626"],
      ["browser-dependent", ($counts.browser_dependent // 0), "#7C3AED"],
      ["unreachable", ($counts.unreachable // 0), "#991B1B"],
      ["unknown", ($counts.unknown // 0), "#6B7280"],
      ["unknown-freshness", ($counts.unknown_freshness // 0), "#6B7280"],
      ["discontinued", ($counts.discontinued // 0), "#6B7280"],
      ["reference", ($counts.reference // 0), "#0EA5E9"]
    ][]
  | select(.[1] | type == "number" and . >= 0 and floor == .)
  | @tsv
' "$health_file")
