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

checked_at="$(jq -r '.checked_at' "$health_file")"
if ! pub_date="$(date -u -d "$checked_at" '+%a, %d %b %Y %H:%M:%S +0000' 2>/dev/null)"; then
  printf 'Invalid checked_at timestamp: %s\n' "$checked_at" >&2
  exit 1
fi

jq -rn \
  --arg pub_date "$pub_date" \
  --arg repository_url "$repository_url" \
  --slurpfile manifest "$manifest" \
  --slurpfile health "$health_file" '
  def xml_escape: @html;
  def valid_status:
    . == "fresh" or . == "aging" or . == "stale" or . == "degraded" or
    . == "browser-dependent" or . == "unreachable" or . == "unknown" or
    . == "unknown-freshness" or . == "reference";
  def item_lines($dataset_id; $name; $status; $message; $item_link):
    "[\($status)] \($name)" as $title |
    "\($name): \($status). \($message)" as $description |
    [
      "    <item>",
      "      <title>\($title | xml_escape)</title>",
      "      <link>\($item_link | xml_escape)</link>",
      "      <guid isPermaLink=\"true\">\($item_link | xml_escape)</guid>",
      "      <description>\($description | xml_escape)</description>",
      "      <pubDate>\($pub_date | xml_escape)</pubDate>",
      "    </item>"
    ];

  $manifest[0] as $manifest_document |
  $health[0] as $health_document |
  [
    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
    "<rss version=\"2.0\">",
    "  <channel>",
    "    <title>DataPulse MY Dataset Health</title>",
    "    <link>https://github.com/r3dz4r/datapulse-my</link>",
    "    <description>Health status for Malaysian public datasets tracked by DataPulse MY.</description>",
    "    <lastBuildDate>\($pub_date | xml_escape)</lastBuildDate>",
    (
      $manifest_document.datasets[] | .id as $dataset_id |
      ([ $manifest_document.datasets[] | select(.id == $dataset_id) ][0].name // $dataset_id) as $name |
      ([ $health_document.datasets[] | select(.dataset_id == $dataset_id) ][0].status // "unknown") as $raw_status |
      ([ $health_document.datasets[] | select(.dataset_id == $dataset_id) ][0].message // "No health data available") as $message |
      (if $raw_status | valid_status then $raw_status else "unknown" end) as $status |
      "\($repository_url)/blob/main/data/\($dataset_id).md" as $item_link |
      item_lines($dataset_id; $name; $status; $message; $item_link)[]
    ),
    "  </channel>",
    "</rss>"
  ] | join("\n")
' > "$output_file"
