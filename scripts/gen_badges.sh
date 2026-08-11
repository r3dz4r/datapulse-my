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

if ! jq -e '.datasets | type == "array"' "$health_file" >/dev/null 2>&1; then
  printf 'Invalid health summary: %s\n' "$health_file" >&2
  exit 1
fi

mkdir -p "$output_dir"

while IFS=$'\t' read -r dataset_id raw_status; do
  if [[ ! "$dataset_id" =~ ^[A-Za-z0-9._-]+$ ]]; then
    printf 'Unsafe dataset id for badge filename: %s\n' "$dataset_id" >&2
    exit 1
  fi

  case "$raw_status" in
    fresh)
      status="fresh"
      color="#3fb950"
      ;;
    aging)
      status="aging"
      color="#d29922"
      ;;
    stale)
      status="stale"
      color="#f85149"
      ;;
    degraded)
      status="degraded"
      color="#a371f7"
      ;;
    unreachable)
      status="unreachable"
      color="#f85149"
      ;;
    browser-dependent)
      status="browser-dependent"
      color="#58a6ff"
      ;;
    unknown-freshness)
      status="unknown-freshness"
      color="#6e7681"
      ;;
    discontinued)
      status="discontinued"
      color="#484f58"
      ;;
    reference)
      status="reference"
      color="#0ea5e9"
      ;;
    *)
      status="unknown"
      color="#6e7681"
      ;;
  esac

  escaped_status="$(jq -rn --arg value "$status" '$value | @html')"
  badge_file="${output_dir}/${dataset_id}.svg"
  stroke_dasharray=""
  if [[ "$status" == "unknown-freshness" ]]; then
    stroke_dasharray=' stroke-dasharray="2,2"'
  fi

  printf '%s\n' \
    '<svg xmlns="http://www.w3.org/2000/svg" width="110" height="20" role="img" aria-label="health: '"$escaped_status"'">' \
    '  <title>health: '"$escaped_status"'</title>' \
    '  <rect x="0.5" y="0.5" width="109" height="19" rx="3" fill="#0d1117" stroke="'"$color"'" stroke-width="1"'"$stroke_dasharray"'/>' \
    '  <g fill="'"$color"'" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="10" font-weight="500">' \
    '    <text x="17.5" y="14">health</text>' \
    '    <text x="72.5" y="14" textLength="68" lengthAdjust="spacingAndGlyphs">'"$escaped_status"'</text>' \
    '  </g>' \
    '</svg>' > "$badge_file"
done < <(jq -r '.datasets[] | [(.dataset_id // ""), (.status // "unknown")] | @tsv' "$health_file")

scripts/gen_status_legend.sh "$health_file"
