#!/usr/bin/env bash
set -euo pipefail

manifest="${1:-datapulse.json}"
results_file="$(mktemp)"
body_file="$(mktemp)"
trap 'rm -f "$results_file" "$body_file"' EXIT

check_eqms_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local wait_seconds="$3"
  local camofox_base_url="${CAMOFOX_BASE_URL:-http://100.74.84.121:9377}"
  local user_id="datapulse-check-${dataset_id}"
  local open_response tab_id snapshot_response snapshot
  local stations timestamp snapshot_chars

  open_response="$(curl --location --silent --show-error --fail \
    --request POST "${camofox_base_url}/tabs/open" \
    --header 'Content-Type: application/json' \
    --data "$(jq -n --arg userId "$user_id" --arg url "$source_url" \
      '{userId: $userId, url: $url}')")" || {
      printf 'Camofox tab open failed for %s (%s)\n' "$dataset_id" "$source_url" >&2
      exit 1
    }

  tab_id="$(jq -r '.tabId // empty' <<< "$open_response")"
  if [[ -z "$tab_id" ]]; then
    printf 'Camofox returned no tab id for %s (%s)\n' "$dataset_id" "$source_url" >&2
    exit 1
  fi

  sleep "$wait_seconds"

  snapshot_response="$(curl --location --silent --show-error --fail \
    "${camofox_base_url}/tabs/${tab_id}/snapshot?userId=${user_id}")" || {
      curl --silent --show-error --request DELETE \
        "${camofox_base_url}/tabs/${tab_id}" \
        --header 'Content-Type: application/json' \
        --data "$(jq -n --arg userId "$user_id" '{userId: $userId}')" >/dev/null || true
      printf 'Camofox snapshot failed for %s (%s)\n' "$dataset_id" "$source_url" >&2
      exit 1
    }

  snapshot="$(jq -r '.snapshot // empty' <<< "$snapshot_response")"
  stations="$(grep -Ec 'row "[0-9]+ [A-Z]' <<< "$snapshot" || true)"
  timestamp="$(grep -Eo '[0-9]{2}/[0-9]{2}/[0-9]{4}, [0-9]{2}:[0-9]{2}' \
    <<< "$snapshot" | head -n 1 || true)"
  snapshot_chars="${#snapshot}"

  curl --silent --show-error --fail --request DELETE \
    "${camofox_base_url}/tabs/${tab_id}" \
    --header 'Content-Type: application/json' \
    --data "$(jq -n --arg userId "$user_id" '{userId: $userId}')" >/dev/null || {
      printf 'Camofox tab close failed for %s (%s)\n' "$dataset_id" "$source_url" >&2
      exit 1
    }

  jq -n \
    --arg dataset_id "$dataset_id" \
    --arg url "$source_url" \
    --arg access_method "Camofox" \
    --argjson wait_seconds "$wait_seconds" \
    --argjson stations "$stations" \
    --arg timestamp "$timestamp" \
    --argjson snapshot_chars "$snapshot_chars" \
    '{
      dataset_id: $dataset_id,
      url: $url,
      access_method: $access_method,
      wait_seconds: $wait_seconds,
      stations: $stations,
      timestamp: (if $timestamp == "" then null else $timestamp end),
      snapshot_chars: $snapshot_chars
    }'
}

while IFS=$'\t' read -r dataset_id source_url; do
  if [[ "$dataset_id" == "doe_apims" ]]; then
    check_eqms_dataset "$dataset_id" "$source_url" 10 >> "$results_file"
    continue
  elif [[ "$dataset_id" == "doe_rqims" ]]; then
    check_eqms_dataset "$dataset_id" "$source_url" 12 >> "$results_file"
    continue
  elif [[ "$dataset_id" == "doe_mqims" ]]; then
    check_eqms_dataset "$dataset_id" "$source_url" 12 >> "$results_file"
    continue
  elif [[ "$dataset_id" == "met_weather" ]]; then
    http_status="$(curl --location --silent --show-error \
      --output "$body_file" --write-out '%{http_code}' "$source_url")" || {
        printf 'curl failed for %s (%s)\n' "$dataset_id" "$source_url" >&2
        exit 1
      }

    if [[ ! "$http_status" =~ ^2[0-9][0-9]$ ]]; then
      printf 'HTTP %s for %s (%s)\n' "$http_status" "$dataset_id" "$source_url" >&2
      exit 1
    fi

    jq -n \
      --arg dataset_id "$dataset_id" \
      --arg url "$source_url" \
      --argjson http_status "$http_status" \
      --argjson content_length "$(wc -c < "$body_file" | tr -d '[:space:]')" \
      --argjson record_count "$(jq 'length' "$body_file")" \
      --argjson locations "$(jq '[.[].location.location_id] | unique | length' "$body_file")" \
      --arg date_start "$(jq -r '[.[].date] | min' "$body_file")" \
      --arg date_end "$(jq -r '[.[].date] | max' "$body_file")" \
      '{
        dataset_id: $dataset_id,
        url: $url,
        request_url: $url,
        http_status: $http_status,
        content_length: $content_length,
        record_count: $record_count,
        locations: $locations,
        date_range: {start: $date_start, end: $date_end}
      }' >> "$results_file"
    continue
  fi

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
