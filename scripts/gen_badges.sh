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
      color="#4c1"
      ;;
    aging)
      status="aging"
      color="#dfb317"
      ;;
    stale)
      status="stale"
      color="#fe7d37"
      ;;
    degraded)
      status="degraded"
      color="#e05d44"
      ;;
    unreachable)
      status="unreachable"
      color="#e05d44"
      ;;
    browser-dependent)
      status="browser-dependent"
      color="#007ec6"
      ;;
    unknown-freshness)
      status="unknown-freshness"
      color="#9f7aea"
      ;;
    *)
      status="unknown"
      color="#9f9f9f"
      ;;
  esac

  escaped_status="$(jq -rn --arg value "$status" '$value | @html')"
  badge_file="${output_dir}/${dataset_id}.svg"

  printf '%s\n' \
    '<svg xmlns="http://www.w3.org/2000/svg" width="110" height="20" role="img" aria-label="health: '"$escaped_status"'">' \
    '  <title>health: '"$escaped_status"'</title>' \
    '  <clipPath id="r"><rect width="110" height="20" rx="3" fill="#fff"/></clipPath>' \
    '  <g clip-path="url(#r)">' \
    '    <rect width="35" height="20" fill="#555"/>' \
    '    <rect x="35" width="75" height="20" fill="'"$color"'"/>' \
    '  </g>' \
    '  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="9">' \
    '    <text x="17.5" y="14">health</text>' \
    '    <text x="72.5" y="14" textLength="68" lengthAdjust="spacingAndGlyphs">'"$escaped_status"'</text>' \
    '  </g>' \
    '</svg>' > "$badge_file"
done < <(jq -r '.datasets[] | [(.dataset_id // ""), (.status // "unknown")] | @tsv' "$health_file")
