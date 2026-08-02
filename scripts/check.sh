#!/usr/bin/env bash
set -euo pipefail

manifest="${1:-datapulse.json}"
results_file="$(mktemp)"
body_file="$(mktemp)"
trap 'rm -f "$results_file" "$body_file"' EXIT

while IFS=$'\t' read -r dataset_id source_url; do
  request_url="$source_url"
  if [[ "$dataset_id" == "fuelprice" ]]; then
    request_url="https://api.data.gov.my/data-catalogue?id=fuelprice&limit=1"
  fi

  http_status="$(curl --location --silent --show-error \
    --output "$body_file" --write-out '%{http_code}' "$request_url")" || {
      printf 'curl failed for %s (%s)\n' "$dataset_id" "$request_url" >&2
      exit 1
    }

  if [[ ! "$http_status" =~ ^2[0-9][0-9]$ ]]; then
    printf 'HTTP %s for %s (%s)\n' "$http_status" "$dataset_id" "$request_url" >&2
    exit 1
  fi

  content_length="$(wc -c < "$body_file" | tr -d '[:space:]')"
  first_record_timestamp="$(
    jq -r 'if type == "array" then .[0] else . end
      | .timestamp // .date // .publish_date // empty' "$body_file" 2>/dev/null || true
  )"

  jq -n \
    --arg dataset_id "$dataset_id" \
    --arg url "$source_url" \
    --arg request_url "$request_url" \
    --argjson http_status "$http_status" \
    --argjson content_length "$content_length" \
    --arg first_record_timestamp "$first_record_timestamp" \
    '{
      dataset_id: $dataset_id,
      url: $url,
      request_url: $request_url,
      http_status: $http_status,
      content_length: $content_length,
      first_record_timestamp: (
        if $first_record_timestamp == "" then null else $first_record_timestamp end
      )
    }' >> "$results_file"
done < <(jq -r '.datasets[] | [.id, .url] | @tsv' "$manifest")

jq -s \
  --arg schema "datapulse/v0.1/dataset-health" \
  --arg checked_at "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
  '{schema: $schema, checked_at: $checked_at, datasets: .}' "$results_file"
