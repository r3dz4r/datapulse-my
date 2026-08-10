#!/usr/bin/env bash
set -euo pipefail

health_file="${1:-health/latest.json}"
manifest="${2:-datapulse.json}"
output_file="feed.xml"
repository_url="https://github.com/r3dz4r/datapulse-my"

if ! command -v jq >/dev/null 2>&1; then
  printf 'jq is required\n' >&2
  exit 1
fi

if [[ ! -r "$health_file" ]]; then
  printf 'Cannot read health summary: %s\n' "$health_file" >&2
  exit 1
fi

if [[ ! -r "$manifest" ]]; then
  printf 'Cannot read manifest: %s\n' "$manifest" >&2
  exit 1
fi

if ! jq -e '.checked_at | type == "string"' "$health_file" >/dev/null 2>&1 || \
  ! jq -e '.datasets | type == "array"' "$health_file" >/dev/null 2>&1; then
  printf 'Invalid health summary: %s\n' "$health_file" >&2
  exit 1
fi

if ! jq -e '.datasets | type == "array"' "$manifest" >/dev/null 2>&1; then
  printf 'Invalid dataset manifest: %s\n' "$manifest" >&2
  exit 1
fi

xml_escape() {
  jq -rn --arg value "$1" '$value | @html'
}

checked_at="$(jq -r '.checked_at' "$health_file")"
if ! pub_date="$(date -u -d "$checked_at" '+%a, %d %b %Y %H:%M:%S +0000' 2>/dev/null)"; then
  printf 'Invalid checked_at timestamp: %s\n' "$checked_at" >&2
  exit 1
fi

{
  printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>'
  printf '%s\n' '<rss version="2.0">'
  printf '%s\n' '  <channel>'
  printf '%s\n' '    <title>DataPulse MY Dataset Health</title>'
  printf '%s\n' '    <link>https://github.com/r3dz4r/datapulse-my</link>'
  printf '%s\n' '    <description>Health status for Malaysian public datasets tracked by DataPulse MY.</description>'
  printf '    <lastBuildDate>%s</lastBuildDate>\n' "$(xml_escape "$pub_date")"

  while IFS= read -r dataset_id; do
    name="$(jq -r --arg id "$dataset_id" \
      '[.datasets[] | select(.id == $id)][0].name // $id' "$manifest")"
    status="$(jq -r --arg id "$dataset_id" \
      '[.datasets[] | select(.dataset_id == $id)][0].status // "unknown"' "$health_file")"
    message="$(jq -r --arg id "$dataset_id" \
      '[.datasets[] | select(.dataset_id == $id)][0].message // "No health data available"' \
      "$health_file")"

    case "$status" in
      fresh|aging|stale|degraded|browser-dependent|unreachable|unknown|unknown-freshness|reference) ;;
      *) status="unknown" ;;
    esac

    item_link="${repository_url}/blob/main/data/${dataset_id}.md"
    title="[${status}] ${name}"
    description="${name}: ${status}. ${message}"

    printf '%s\n' '    <item>'
    printf '      <title>%s</title>\n' "$(xml_escape "$title")"
    printf '      <link>%s</link>\n' "$(xml_escape "$item_link")"
    printf '      <guid isPermaLink="true">%s</guid>\n' "$(xml_escape "$item_link")"
    printf '      <description>%s</description>\n' "$(xml_escape "$description")"
    printf '      <pubDate>%s</pubDate>\n' "$(xml_escape "$pub_date")"
    printf '%s\n' '    </item>'
  done < <(jq -r '.datasets[].id' "$manifest")

  printf '%s\n' '  </channel>'
  printf '%s\n' '</rss>'
} > "$output_file"
