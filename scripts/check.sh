#!/usr/bin/env bash
# Dataset failures are data: record them and continue so the summary is complete.

due_mode=false
tier_filter=""
cadence_override=""
manifest="datapulse.json"

usage() {
  printf 'Usage: %s [--due [--tier <name>] [--cadence-minutes <n>]] [manifest]\n' "$0" >&2
}

while (( $# > 0 )); do
  case "$1" in
    --due)
      due_mode=true
      shift
      ;;
    --tier)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      tier_filter="$2"
      shift 2
      ;;
    --cadence-minutes)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      cadence_override="$2"
      shift 2
      ;;
    -*)
      usage
      exit 2
      ;;
    *)
      [[ "$manifest" == "datapulse.json" ]] || { usage; exit 2; }
      manifest="$1"
      shift
      ;;
  esac
done

if [[ -n "$tier_filter" && ! "$tier_filter" =~ ^(realtime|daily|weekly-monthly|slow)$ ]]; then
  printf 'Invalid tier: %s\n' "$tier_filter" >&2
  exit 2
fi
if [[ -n "$cadence_override" && ! "$cadence_override" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Invalid cadence minutes: %s\n' "$cadence_override" >&2
  exit 2
fi
if ! $due_mode && [[ -n "$tier_filter" || -n "$cadence_override" ]]; then
  printf '%s requires --due\n' "--tier/--cadence-minutes" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v jq >/dev/null 2>&1; then
  printf 'jq is required\n' >&2
  exit 1
fi

if [[ ! -r "$manifest" ]]; then
  printf 'Cannot read manifest: %s\n' "$manifest" >&2
  exit 1
fi

if ! jq -e '.datasets | type == "array" and all(.[]; (.id | type == "string") and (.url | type == "string"))' \
  "$manifest" >/dev/null 2>&1; then
  printf 'Invalid dataset manifest: %s\n' "$manifest" >&2
  exit 1
fi

results_file="$(mktemp)"
body_file="$(mktemp)"
content_body_file="$(mktemp)"
headers_file="$(mktemp)"
previous_file="$(mktemp)"
selected_manifest_file="$(mktemp)"
probe_results_dir="$(mktemp -d)"
trap 'rm -f "$results_file" "$body_file" "$content_body_file" "$headers_file" "$previous_file" "$selected_manifest_file"; rm -rf "$probe_results_dir"' EXIT

if [[ -s health/latest.json ]]; then
  cp health/latest.json "$previous_file"
elif command -v git >/dev/null 2>&1; then
  git show HEAD:health/latest.json > "$previous_file" 2>/dev/null || true
fi

if $due_mode; then
  now_epoch="$(date -u +%s)"
  jq \
    --slurpfile previous "$previous_file" \
    --arg tier_filter "$tier_filter" \
    --arg cadence_override "$cadence_override" \
    --argjson now_epoch "$now_epoch" \
    '
    def tier_and_cadence($frequency):
      ($frequency // "" | ascii_downcase) as $frequency
      | if $frequency == "30 seconds" or $frequency == "hourly" then ["realtime", 15]
        elif $frequency == "daily" or ($frequency | startswith("daily (weekdays,")) then ["daily", 1440]
        elif $frequency == "weekly" or $frequency == "monthly" or $frequency == "quarterly" then ["weekly-monthly", 10080]
        elif $frequency == "annual" or $frequency == "biennial to triennial (survey years)" or $frequency == "as-required" then ["slow", 43200]
        else error("Unsupported refresh_frequency: \($frequency)")
        end;

    ((($previous[0] // {}).datasets) // []) as $previous_rows
    | .datasets |= map(
        . as $entry
        | tier_and_cadence($entry.refresh_frequency) as $schedule
        | (first($previous_rows[] | select(.dataset_id == $entry.id)) // {}) as $old
        | (if $cadence_override == "" then $schedule[1] else ($cadence_override | tonumber) end) as $cadence_minutes
        | (try ($old.last_checked | fromdateiso8601) catch null) as $last_checked_epoch
        | select(($tier_filter == "" or $schedule[0] == $tier_filter)
            and ($last_checked_epoch == null or ($now_epoch - $last_checked_epoch) >= ($cadence_minutes * 60)))
      )
    ' "$manifest" > "$selected_manifest_file"
else
  cp "$manifest" "$selected_manifest_file"
fi

curl_timeout="${DATAPULSE_CURL_TIMEOUT:-30}"
gtfs_timeout="${DATAPULSE_GTFS_TIMEOUT:-45}"
camofox_timeout="${CAMOFOX_TIMEOUT:-12}"
camofox_base_url="${CAMOFOX_BASE_URL:-http://100.74.84.121:9377}"

declare -A DATASET_CONTENT_DATE_FIELDS=(
  [fuelprice]=date
  [pricecatcher]=date
  [exchangerates_daily_0900]=date
  [exchangerates_daily_1130]=date
  [exchangerates_daily_1200]=date
  [exchangerates_daily_1700]=date
)

declare -A DATASET_BROWSER_DATE_REGEX=(
  [doe_apims]='[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
  [doe_rqims]='[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
  [doe_mqims]='[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
  [kkm_idengue]='[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
  [eperolehan-diklankan]='[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}|[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}'
)

extract_max_date() {
  local body_path="$1"
  local date_field="$2"

  jq -r --arg f "$date_field" '
    if type == "array" then
      [.[].[$f]] | map(select(. != null)) | max
    elif type == "object" then
      [.[$f]] | map(select(. != null)) | max
    else null
    end
  ' "$body_path"
}

extract_json_metrics() {
  local body_path="$1"

  # CSV body fallback: jq can't parse CSV directly, but `wc -l` counts rows
  # (including a partial last line). If the body isn't JSON, treat it as
  # text and count newlines. We need this because the dgm_/dosm_ manifests
  # point at .csv direct-download files on storage.dosm.gov.my and
  # storage.data.gov.my. Estimated true row count = newlines - 1 (header).
  # Note: redirect stderr to /dev/null because parquet / binary bodies
  # cause bash to emit "ignored null byte" warnings that otherwise leak
  # into our stdout JSON envelope.
  if ! jq -e . "$body_path" >/dev/null 2>&1; then
    local line_count column_count header_line
    line_count="$(wc -l < "$body_path" 2>/dev/null | tr -d '[:space:]')"
    header_line="$(head -n 1 "$body_path" 2>/dev/null | tr -d '\0' | head -c 4000 || true)"
    if [[ "$line_count" =~ ^[0-9]+$ ]] && (( line_count > 0 )); then
      # heuristic: any line without a comma is probably not CSV; refuse to
      # report a count for it. most CSV files have comma-delimited headers.
      if [[ "$header_line" == *,* ]]; then
        column_count="$(printf '%s' "$header_line" | awk -F',' '{print NF}')"
        [[ -z "$column_count" || ! "$column_count" =~ ^[0-9]+$ ]] && column_count="null"
        jq -c -n \
          --argjson rc "$(( line_count - 1 ))" \
          --argjson cc "$column_count" \
          '{
            record_count: (if $rc >= 0 then $rc else null end),
            column_count: $cc,
            first_row: null,
            first_record_timestamp: null,
            body_format: "csv"
          }' 2>/dev/null
        return 0
      fi
    fi
  fi

  jq -c '
    def wrapped_rows:
      if type == "array" then .
      elif type == "object" then
        [.data, .result, .results, .records, .items, .rows]
        | map(select(. != null and type == "array"))
        | first
      else null
      end;

    . as $document
    | wrapped_rows as $rows
    | ($rows[0] // null) as $first_row
    | {
        record_count: (
          if ($rows | type) == "array" then ($rows | length)
          elif ($document | type) == "object" then ($document | length)
          else null
          end
        ),
        column_count: (
          if ($first_row | type) == "object" then ($first_row | keys | length)
          else null
          end
        ),
        first_row: $first_row,
        first_record_timestamp: (
          if ($first_row | type) == "object" then
            ($first_row.timestamp // $first_row.date // $first_row.publish_date // null)
          else null
          end
        ),
        body_format: "json"
      }
  ' "$body_path" 2>/dev/null \
    || printf '{"record_count":null,"column_count":null,"first_row":null,"first_record_timestamp":null,"body_format":"unknown"}\n'
}

estimate_parquet_rows() {
  local content_length="$1"

  if [[ "$content_length" =~ ^[0-9]+$ ]] && (( content_length > 16 )); then
    jq -n --argjson bytes "$content_length" '(($bytes - 16) / 120 | ceil)'
  else
    printf 'null\n'
  fi
}

extract_browser_dates() {
  local snapshot_file="$1"
  local date_regex="$2"
  local matched_date year month day iso_date parsed_date
  local today

  today="$(date -u +'%Y-%m-%d')"

  while IFS= read -r matched_date; do
    if [[ "$matched_date" =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})$ ]]; then
      year="${BASH_REMATCH[1]}"
      month="${BASH_REMATCH[2]}"
      day="${BASH_REMATCH[3]}"
    elif [[ "$matched_date" =~ ^([0-9]{1,2})[/\-]([0-9]{1,2})[/\-]([0-9]{4})$ ]]; then
      day="${BASH_REMATCH[1]}"
      month="${BASH_REMATCH[2]}"
      year="${BASH_REMATCH[3]}"
    else
      continue
    fi

    printf -v iso_date '%04d-%02d-%02d' "$((10#$year))" "$((10#$month))" "$((10#$day))"
    parsed_date="$(date -u -d "$iso_date" +'%Y-%m-%d' 2>/dev/null)" || continue
    [[ "$parsed_date" > "$today" ]] || printf '%s\n' "$parsed_date"
  done < <(grep -oE "$date_regex" "$snapshot_file" || true) | sort -u | tail -1
}

emit() {
  local dataset_id="$1"
  local url="$2"
  local status="$3"
  local message="$4"
  local details="${5:-\{\}}"

  jq -cn \
    --arg dataset_id "$dataset_id" \
    --arg url "$url" \
    --arg status "$status" \
    --arg message "$message" \
    --argjson details "$details" \
    '{dataset_id: $dataset_id, url: $url, status: $status, message: $message} + $details' \
    >> "$results_file"
}

http_status_name() {
  local http_status="$1"

  case "$http_status" in
    2??) printf 'fresh' ;;
    4??|5??) printf 'unreachable' ;;
    *) printf 'unknown' ;;
  esac
}

emit_http_failure() {
  local dataset_id="$1"
  local source_url="$2"
  local request_url="$3"
  local http_status="$4"
  local access_method="${5:-direct curl GET}"
  local status details

  status="$(http_status_name "$http_status")"
  details="$(jq -cn \
    --arg request_url "$request_url" \
    --arg access_method "$access_method" \
    --argjson http_status "$http_status" \
    '{request_url: $request_url, access_method: $access_method, http_status: $http_status}')"
  emit "$dataset_id" "$source_url" "$status" "HTTP ${http_status}" "$details"
}

close_camofox_tab() {
  local tab_id="$1"
  local user_id="$2"

  curl --silent --show-error --fail --max-time "$camofox_timeout" \
    --request DELETE "${camofox_base_url}/tabs/${tab_id}" \
    --header 'Content-Type: application/json' \
    --data "$(jq -cn --arg userId "$user_id" '{userId: $userId}')" >/dev/null 2>&1
}

warm_camofox_browser() {
  local user_id="datapulse-check-warmup"
  local open_response tab_id

  # Boot Camofox once before browser checks to prevent cold-start flapping.
  if ! open_response="$(curl --location --silent --show-error --fail \
    --max-time "$camofox_timeout" \
    --request POST "${camofox_base_url}/tabs/open" \
    --header 'Content-Type: application/json' \
    --data "$(jq -cn --arg userId "$user_id" --arg url 'about:blank' \
      '{userId: $userId, url: $url}')" 2>/dev/null)"; then
    return 0
  fi

  tab_id="$(jq -r '.tabId // empty' <<< "$open_response" 2>/dev/null)"
  [[ -n "$tab_id" ]] || return 0

  sleep 5
  close_camofox_tab "$tab_id" "$user_id" || true
}

check_browser_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local wait_seconds="$3"
  local user_id="datapulse-check-${dataset_id}"
  local open_response tab_id snapshot_response snapshot details
  local stations timestamp snapshot_chars content_freshness_date date_regex

  if ! open_response="$(curl --location --silent --show-error --fail \
    --max-time "$camofox_timeout" \
    --request POST "${camofox_base_url}/tabs/open" \
    --header 'Content-Type: application/json' \
    --data "$(jq -cn --arg userId "$user_id" --arg url "$source_url" \
      '{userId: $userId, url: $url}')" 2>/dev/null)"; then
    sleep 2
    if ! open_response="$(curl --location --silent --show-error --fail \
      --max-time "$camofox_timeout" \
      --request POST "${camofox_base_url}/tabs/open" \
      --header 'Content-Type: application/json' \
      --data "$(jq -cn --arg userId "$user_id" --arg url "$source_url" \
        '{userId: $userId, url: $url}')" 2>/dev/null)"; then
      details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
      emit "$dataset_id" "$source_url" "browser-dependent" \
        "Camofox unavailable; browser check required" "$details"
      return 0
    fi
  fi

  tab_id="$(jq -r '.tabId // empty' <<< "$open_response" 2>/dev/null)"
  if [[ -z "$tab_id" ]]; then
    details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
    emit "$dataset_id" "$source_url" "browser-dependent" "Camofox returned no tab id" "$details"
    return 0
  fi

  sleep "$wait_seconds"

  if ! snapshot_response="$(curl --location --silent --show-error --fail \
    --max-time "$camofox_timeout" \
    "${camofox_base_url}/tabs/${tab_id}/snapshot?userId=${user_id}" 2>/dev/null)"; then
    sleep 2
    if ! snapshot_response="$(curl --location --silent --show-error --fail \
      --max-time "$camofox_timeout" \
      "${camofox_base_url}/tabs/${tab_id}/snapshot?userId=${user_id}" 2>/dev/null)"; then
      close_camofox_tab "$tab_id" "$user_id" || true
      details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
      emit "$dataset_id" "$source_url" "browser-dependent" "Camofox snapshot failed" "$details"
      return 0
    fi
  fi

  snapshot="$(jq -r '.snapshot // empty' <<< "$snapshot_response" 2>/dev/null)"
  if [[ -z "$snapshot" ]]; then
    close_camofox_tab "$tab_id" "$user_id" || true
    details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
    emit "$dataset_id" "$source_url" "browser-dependent" "Camofox returned no snapshot" "$details"
    return 0
  fi

  stations="$(grep -Ec 'row "[0-9]+ [A-Z]' <<< "$snapshot" || true)"
  timestamp="$(grep -Eo '[0-9]{2}/[0-9]{2}/[0-9]{4}, [0-9]{2}:[0-9]{2}' \
    <<< "$snapshot" | head -n 1 || true)"
  snapshot_chars="${#snapshot}"
  printf '%s' "$snapshot" > "$body_file"
  date_regex="${DATASET_BROWSER_DATE_REGEX[$dataset_id]:-}"
  content_freshness_date="$(extract_browser_dates "$body_file" "$date_regex")"

  if ! close_camofox_tab "$tab_id" "$user_id"; then
    details="$(jq -cn \
      --arg access_method 'Camofox' \
      --argjson wait_seconds "$wait_seconds" \
      '{access_method: $access_method, wait_seconds: $wait_seconds}')"
    emit "$dataset_id" "$source_url" "browser-dependent" "Camofox tab close failed" "$details"
    return 0
  fi

  details="$(jq -cn \
    --arg access_method 'Camofox' \
    --argjson wait_seconds "$wait_seconds" \
    --argjson stations "$stations" \
    --arg timestamp "$timestamp" \
    --argjson snapshot_chars "$snapshot_chars" \
    --arg content_freshness_date "$content_freshness_date" \
    '{
      access_method: $access_method,
      wait_seconds: $wait_seconds,
      stations: $stations,
      timestamp: (if $timestamp == "" then null else $timestamp end),
      snapshot_chars: $snapshot_chars,
      content_freshness_date: (
        if $content_freshness_date == "" then null else $content_freshness_date end
      )
    }')"
  emit "$dataset_id" "$source_url" "browser-dependent" "Browser check succeeded" "$details"
}

check_head_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local request_url catalogue_id http_status status content_length last_modified details
  local api_http_status metrics record_count column_count first_row first_row_hash
  local first_record_timestamp estimated_record_count record_count_estimated incomplete

  : > "$headers_file"
  if ! http_status="$(curl --location --silent --show-error --head \
    --max-time "$curl_timeout" \
    --dump-header "$headers_file" --output /dev/null --write-out '%{http_code}' \
    "$source_url" 2>/dev/null)"; then
    details="$(jq -cn --arg access_method 'direct curl HEAD' \
      '{access_method: $access_method}')"
    emit "$dataset_id" "$source_url" "unreachable" "curl HEAD request failed" "$details"
    return 0
  fi

  status="$(http_status_name "$http_status")"
  if [[ "$status" != "fresh" ]]; then
    emit_http_failure "$dataset_id" "$source_url" "$source_url" "$http_status" \
      "direct curl HEAD"
    return 0
  fi

  content_length="$(awk 'BEGIN { IGNORECASE=1 } /^content-length:/ { value=$2 } END { gsub("\\r", "", value); print value }' "$headers_file")"
  last_modified="$(awk 'BEGIN { IGNORECASE=1 } /^last-modified:/ { sub(/^[^:]+:[[:space:]]*/, ""); value=$0 } END { gsub("\\r", "", value); print value }' "$headers_file")"

  [[ "$content_length" =~ ^[0-9]+$ ]] || content_length="null"
  if [[ -n "$last_modified" ]]; then
    last_modified="$(date -u -d "$last_modified" +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || true)"
  fi

  catalogue_id="${source_url%%\?*}"
  catalogue_id="${catalogue_id##*/}"
  catalogue_id="${catalogue_id%.csv}"
  catalogue_id="${catalogue_id%.parquet}"
  if [[ "$dataset_id" == dosm_* ]]; then
    request_url="https://api.data.gov.my/opendosm?id=${catalogue_id}&limit=10000"
  else
    request_url="https://api.data.gov.my/data-catalogue?id=${catalogue_id}&limit=10000"
  fi
  record_count="null"
  column_count="null"
  first_row_hash=""
  first_record_timestamp=""
  estimated_record_count="null"
  record_count_estimated="false"
  incomplete="false"

  if api_http_status="$(curl --location --silent --show-error \
    --max-time "$curl_timeout" --output "$body_file" --write-out '%{http_code}' \
    "$request_url" 2>/dev/null)" && [[ "$api_http_status" =~ ^2[0-9][0-9]$ ]]; then
    metrics="$(extract_json_metrics "$body_file")"
    record_count="$(jq '.record_count' <<< "$metrics")"
    column_count="$(jq '.column_count' <<< "$metrics")"
    first_row="$(jq -cS '.first_row' <<< "$metrics")"
    first_record_timestamp="$(jq -r '.first_record_timestamp // empty' <<< "$metrics")"
    if [[ "$first_row" != "null" ]]; then
      first_row_hash="$(printf '%s' "$first_row" | sha256sum | awk '{print $1}')"
    fi
    if [[ "$record_count" =~ ^[0-9]+$ ]] && (( record_count >= 10000 )); then
      incomplete="true"
    fi
  fi

  if { [[ "$record_count" == "null" ]] || [[ "$record_count" == "0" ]]; } \
    && [[ "${source_url%%\?*}" == *.parquet ]]; then
    estimated_record_count="$(estimate_parquet_rows "$content_length")"
    if [[ "$estimated_record_count" != "null" ]]; then
      record_count="$estimated_record_count"
      record_count_estimated="true"
      incomplete="true"
    fi
  fi

  details="$(jq -cn \
    --arg access_method 'direct curl HEAD + API GET' \
    --arg request_url "$request_url" \
    --argjson http_status "$http_status" \
    --argjson content_length "$content_length" \
    --argjson record_count "$record_count" \
    --argjson column_count "$column_count" \
    --arg first_row_hash "$first_row_hash" \
    --arg first_record_timestamp "$first_record_timestamp" \
    --argjson estimated_record_count "$estimated_record_count" \
    --argjson record_count_estimated "$record_count_estimated" \
    --argjson incomplete "$incomplete" \
    --arg last_modified "$last_modified" \
    '{
      access_method: $access_method,
      request_url: $request_url,
      http_status: $http_status,
      content_length: $content_length,
      record_count: $record_count,
      column_count: $column_count,
      first_row_hash: (if $first_row_hash == "" then null else $first_row_hash end),
      first_record_timestamp: (
        if $first_record_timestamp == "" then null else $first_record_timestamp end
      ),
      estimated_record_count: $estimated_record_count,
      record_count_estimated: $record_count_estimated,
      incomplete: $incomplete,
      last_modified: (if $last_modified == "" then null else $last_modified end)
    }')"
  emit "$dataset_id" "$source_url" "fresh" "HTTP ${http_status}" "$details"
}

check_weather_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local http_status content_length record_count locations date_start date_end details
  local content_freshness_date
  local column_count first_row_hash

  if ! http_status="$(curl --location --silent --show-error \
    --max-time "$curl_timeout" \
    --output "$body_file" --write-out '%{http_code}' "$source_url" 2>/dev/null)"; then
    emit "$dataset_id" "$source_url" "unreachable" "curl request failed" \
      '{"access_method":"direct curl GET"}'
    return 0
  fi

  if [[ ! "$http_status" =~ ^2[0-9][0-9]$ ]]; then
    emit_http_failure "$dataset_id" "$source_url" "$source_url" "$http_status"
    return 0
  fi

  if ! jq -e 'type == "array"' "$body_file" >/dev/null 2>&1; then
    details="$(jq -cn --argjson http_status "$http_status" \
      '{access_method: "direct curl GET", http_status: $http_status}')"
    emit "$dataset_id" "$source_url" "degraded" "Response was not a JSON array" "$details"
    return 0
  fi

  content_length="$(wc -c < "$body_file" | tr -d '[:space:]')"
  record_count="$(jq 'length' "$body_file")"
  column_count="$(jq 'if length > 0 and (.[0] | type) == "object" then (.[0] | keys | length) else null end' "$body_file")"
  first_row_hash="$(jq -cS '.[0] // null' "$body_file" | sha256sum | awk '{print $1}')"
  locations="$(jq '[.[].location.location_id] | unique | length' "$body_file")"
  date_start="$(jq -r '[.[].date] | min // empty' "$body_file")"
  date_end="$(jq -r '[.[].date] | max // empty' "$body_file")"
  content_freshness_date="$(DATAPULSE_CONTENT_FILE="$body_file" \
    "$script_dir/extract_content_freshness.sh" "$source_url" "$dataset_id" || true)"
  details="$(jq -cn \
    --arg request_url "$source_url" \
    --argjson http_status "$http_status" \
    --argjson content_length "$content_length" \
    --argjson record_count "$record_count" \
    --argjson column_count "$column_count" \
    --arg first_row_hash "$first_row_hash" \
    --argjson locations "$locations" \
    --arg date_start "$date_start" \
    --arg date_end "$date_end" \
    --arg content_freshness_date "$content_freshness_date" \
    '{
      request_url: $request_url,
      access_method: "direct curl GET",
      http_status: $http_status,
      content_length: $content_length,
      record_count: $record_count,
      column_count: $column_count,
      first_row_hash: $first_row_hash,
      locations: $locations,
      date_range: {start: ($date_start // null), end: ($date_end // null)},
      content_freshness_date: (
        if $content_freshness_date == "" then null else $content_freshness_date end
      )
    }')"
  emit "$dataset_id" "$source_url" "fresh" "HTTP ${http_status}" "$details"
}

check_direct_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local request_url="$source_url"
  local http_status content_length first_record_timestamp details last_modified
  local content_freshness_date content_request_url date_field
  local metrics record_count column_count first_row_hash first_row
  local estimated_record_count record_count_estimated incomplete

  date_field="${DATASET_CONTENT_DATE_FIELDS[$dataset_id]:-}"
  # date_field is used later to parse the body's freshness date column.
  # We do NOT override the manifest URL here — direct-storage URLs in
  # the manifest are now the canonical source (the legacy data-catalogue
  # API was decommissioned).

  : > "$headers_file"
  if ! http_status="$(curl --location --silent --show-error \
    --max-time "$curl_timeout" \
    --dump-header "$headers_file" \
    --output "$body_file" --write-out '%{http_code}' "$request_url" 2>/dev/null)"; then
    details="$(jq -cn --arg request_url "$request_url" \
      '{request_url: $request_url, access_method: "direct curl GET"}')"
    emit "$dataset_id" "$source_url" "unreachable" "curl request failed" "$details"
    return 0
  fi

  # The catalogue API currently has no pricecatcher route. Preserve the S3
  # availability/header probe while retaining the configured content attempt.
  if [[ "$dataset_id" == "pricecatcher" && ! "$http_status" =~ ^2[0-9][0-9]$ ]]; then
    request_url="$source_url"
    : > "$headers_file"
    if ! http_status="$(curl --location --silent --show-error \
      --max-time "$curl_timeout" \
      --dump-header "$headers_file" \
      --output "$body_file" --write-out '%{http_code}' "$request_url" 2>/dev/null)"; then
      details="$(jq -cn --arg request_url "$request_url" \
        '{request_url: $request_url, access_method: "direct curl GET"}')"
      emit "$dataset_id" "$source_url" "unreachable" "curl request failed" "$details"
      return 0
    fi
  fi

  if [[ ! "$http_status" =~ ^2[0-9][0-9]$ ]]; then
    emit_http_failure "$dataset_id" "$source_url" "$request_url" "$http_status"
    return 0
  fi

  last_modified="$(awk 'BEGIN { IGNORECASE=1 } /^last-modified:/ { sub(/^[^:]+:[[:space:]]*/, ""); value=$0 } END { gsub("\\r", "", value); print value }' "$headers_file")"
  if [[ -n "$last_modified" ]]; then
    last_modified="$(date -u -d "$last_modified" +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || true)"
  fi

  content_length="$(wc -c < "$body_file" | tr -d '[:space:]')"
  metrics="$(extract_json_metrics "$body_file")"
  record_count="$(jq '.record_count' <<< "$metrics")"
  column_count="$(jq '.column_count' <<< "$metrics")"
  first_row="$(jq -cS '.first_row' <<< "$metrics")"
  estimated_record_count="null"
  record_count_estimated="false"
  incomplete="false"
  if [[ "$record_count" == "null" && "${request_url%%\?*}" == *.parquet ]]; then
    estimated_record_count="$(estimate_parquet_rows "$content_length")"
    if [[ "$estimated_record_count" != "null" ]]; then
      record_count="$estimated_record_count"
      record_count_estimated="true"
      incomplete="true"
    fi
  fi
  if [[ "$first_row" != "null" ]]; then
    first_row_hash="$(printf '%s' "$first_row" | sha256sum | awk '{print $1}')"
  else
    first_row_hash=""
  fi
  first_record_timestamp="$(jq -r '.first_record_timestamp // empty' <<< "$metrics")"
  content_freshness_date=""
  if [[ -n "$content_request_url" ]] && curl --location --silent --show-error --fail \
    --max-time "$curl_timeout" --output "$content_body_file" "$content_request_url" 2>/dev/null; then
    content_freshness_date="$(extract_max_date "$content_body_file" "$date_field")"
  elif [[ -n "$date_field" ]] && jq -e . "$body_file" >/dev/null 2>&1; then
    content_freshness_date="$(extract_max_date "$body_file" "$date_field")"
  fi
  if [[ -n "$content_freshness_date" ]]; then
    [[ "$content_freshness_date" != "null" ]] || content_freshness_date=""
  fi
  details="$(jq -cn \
    --arg request_url "$request_url" \
    --argjson http_status "$http_status" \
    --argjson content_length "$content_length" \
    --argjson record_count "$record_count" \
    --argjson column_count "$column_count" \
    --arg first_row_hash "$first_row_hash" \
    --arg first_record_timestamp "$first_record_timestamp" \
    --argjson estimated_record_count "$estimated_record_count" \
    --argjson record_count_estimated "$record_count_estimated" \
    --argjson incomplete "$incomplete" \
    --arg last_modified "$last_modified" \
    --arg content_freshness_date "$content_freshness_date" \
    '{
      request_url: $request_url,
      access_method: "direct curl GET",
      http_status: $http_status,
      content_length: $content_length,
      record_count: $record_count,
      estimated_record_count: $estimated_record_count,
      record_count_estimated: $record_count_estimated,
      incomplete: $incomplete,
      column_count: $column_count,
      last_modified: (if $last_modified == "" then null else $last_modified end),
      content_freshness_date: (
        if $content_freshness_date == "" then null else $content_freshness_date end
      ),
      first_row_hash: (if $first_row_hash == "" then null else $first_row_hash end),
      first_record_timestamp: (
        if $first_record_timestamp == "" then null else $first_record_timestamp end
      )
    }')"
  emit "$dataset_id" "$source_url" "fresh" "HTTP ${http_status}" "$details"
}

check_gtfs_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local sample_path gtfs_result_file

  if [[ "$dataset_id" == gtfs_static_* ]]; then
    sample_path="samples/gtfs-static/${dataset_id}.zip"
  else
    sample_path="samples/gtfs-realtime/${dataset_id}.pb"
  fi

  gtfs_result_file="${results_file}.gtfs"
  if ! python3 "$script_dir/probe_gtfs.py" \
    "$dataset_id" "$source_url" --sample "$sample_path" --timeout "$gtfs_timeout" \
    > "$gtfs_result_file"; then
    emit "$dataset_id" "$source_url" "unreachable" "GTFS probe helper failed" \
      '{"access_method":"direct curl"}'
  elif [[ "$dataset_id" == gtfs_realtime_* ]]; then
    jq -c '
      if (.content_length | type) == "number" then
        .estimated_record_count = (.content_length / 120)
        | if (.record_count | type) == "number" then
            .record_count_estimated = false
          else
            .record_count = .estimated_record_count
            | .record_count_estimated = true
          end
      else .
      end
    ' "$gtfs_result_file" >> "$results_file"
  else
    cat "$gtfs_result_file" >> "$results_file"
  fi
}

dispatch_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local dataset_result_file="$3"

  results_file="$dataset_result_file"
  body_file="${dataset_result_file}.body"
  content_body_file="${dataset_result_file}.content"
  headers_file="${dataset_result_file}.headers"
  : > "$results_file"

  case "$dataset_id" in
    pricecatcher)
      source_url="https://storage.data.gov.my/pricecatcher/pricecatcher_$(date -u +%Y-%m).parquet"
      check_direct_dataset "$dataset_id" "$source_url"
      ;;
    gtfs_*)
      check_gtfs_dataset "$dataset_id" "$source_url"
      ;;
    doe_apims)
      check_browser_dataset "$dataset_id" "$source_url" 12
      ;;
    doe_rqims|doe_mqims|kkm_idengue|eperolehan-diklankan)
      check_browser_dataset "$dataset_id" "$source_url" 12
      ;;
    dosm_crime_district|dosm_cpi_state|dosm_gdp_state_real_supply|\
    dosm_gdp_qtr_real|dosm_gdp_annual_real_supply|dosm_trade_headline|\
    dosm_cpi_inflation|dosm_trade_enduse_bec|dosm_lfs_qtr|\
    dosm_lfs_qtr_state|dosm_employment_sector|dosm_population_state|\
    dosm_gdp_annual_nominal_supply|dosm_gdp_qtr_nominal|\
    dosm_gdp_qtr_real_sa|dosm_gdp_gni_annual_nominal|\
    dosm_cpi_core_inflation|dosm_cpi_state_inflation|dosm_ppi|\
    dosm_lfs_year|dosm_lfs_month|dosm_trade_sitc_1d|dosm_ipi_export|\
    dosm_ipi_domestic|dgm_interest_rates|dgm_federal_finance_qtr_revenue|\
    dgm_federal_finance_qtr_oe|dgm_state_finance_expenditure|\
    dgm_money_aggregates|dgm_currency_in_circulation|dgm_payments_systems|\
    dgm_payments_instruments|dgm_payments_channels|dgm_interest_rates_annual|\
    dgm_epf_dividend|dgm_vehicle_registrations_type_fuel|\
    dgm_payments_transactions_fpx|dgm_hospital_beds|dgm_healthcare_staff|\
    dgm_blood_donations_state|dgm_infant_immunisation|dgm_std_state|\
    dgm_pekab40_screenings_state|dgm_mnha|dgm_electricity_consumption|\
    dgm_electricity_supply|dgm_water_consumption|dgm_water_production|\
    dgm_water_access|dgm_ridership_headline|dgm_ktmb_ridership_monthly|\
    dgm_cellular_subscribers|dgm_prisoners_state|dgm_drug_addicts_age|\
    dgm_local_authority_sex|dgm_parliament_sex|dgm_fish_landings|\
    dgm_crops_state|dgm_schools_district|dosm_hh_income|dosm_hh_income_state|\
    dosm_hh_income_district|dosm_hh_poverty|dosm_hh_poverty_state|\
    dosm_hh_poverty_district|dosm_hh_inequality|dosm_hh_inequality_state|\
    dosm_hh_inequality_district|dosm_hh_expenditure_dun|\
    dosm_hh_expenditure_parlimen|dosm_population_malaysia|\
    dosm_population_parlimen|dosm_death_district_sex|\
    dosm_marriages_state_age|dosm_fertility|dosm_death_maternal|\
    dosm_birth_state|dosm_death_state|\
    dosm_death_maternal_state|dosm_marriages_state)
      check_direct_dataset "$dataset_id" "$source_url"
      ;;
    met_weather)
      check_weather_dataset "$dataset_id" "$source_url"
      ;;
    *)
      check_direct_dataset "$dataset_id" "$source_url"
      ;;
  esac
}

if jq -e '[.datasets[].id] | any(. == "doe_apims" or . == "doe_rqims" or . == "doe_mqims" or . == "kkm_idengue" or . == "eperolehan-diklankan")' \
  "$selected_manifest_file" >/dev/null; then
  warm_camofox_browser
fi

max_parallel="${DATAPULSE_MAX_PARALLEL:-16}"
active_jobs=0
dataset_index=0
while IFS=$'\t' read -r dataset_id source_url; do
  printf -v result_path '%s/%03d.json' "$probe_results_dir" "$dataset_index"
  dispatch_dataset "$dataset_id" "$source_url" "$result_path" &
  ((active_jobs += 1))
  ((dataset_index += 1))
  if (( active_jobs >= max_parallel )); then
    wait -n
    ((active_jobs -= 1))
  fi
done < <(jq -r '.datasets[] | [.id, .url] | @tsv' "$selected_manifest_file")
wait

: > "$results_file"
if (( dataset_index > 0 )); then
  for result_path in "$probe_results_dir"/*.json; do
    cat "$result_path" >> "$results_file"
  done
fi

expected_count="$(jq '.datasets | length' "$selected_manifest_file")"
actual_count="$(wc -l < "$results_file" | tr -d '[:space:]')"
if [[ "$actual_count" != "$expected_count" ]]; then
  printf 'Internal error: expected %s results, wrote %s\n' "$expected_count" "$actual_count" >&2
  exit 1
fi

if $due_mode && (( expected_count == 0 )) && [[ -s "$previous_file" ]]; then
  cat "$previous_file"
  exit 0
fi

checked_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
checked_epoch="$(date -u -d "$checked_at" +%s)"
jq -s \
  --slurpfile manifest "$manifest" \
  --slurpfile previous "$previous_file" \
  --arg schema "datapulse/v0.3/dataset-health" \
  --arg checked_at "$checked_at" \
  --argjson checked_epoch "$checked_epoch" \
  --argjson due_mode "$due_mode" \
  '
  def cadence_days($frequency):
    ($frequency // "" | ascii_downcase) as $frequency
    | if $frequency | startswith("daily") then 1
      elif $frequency == "weekly" then 7
      elif $frequency == "monthly" then 30
      elif $frequency == "quarterly" then 90
      elif $frequency == "annual" then 365
      else null
      end;
  def status_key($status):
    $status | gsub("-"; "_");

  ($manifest[0].datasets // []) as $manifest_rows
  | ((($previous[0] // {}).datasets) // []) as $previous_rows
  | map(
      . as $probe
      | ($manifest_rows[] | select(.id == $probe.dataset_id)) as $entry
      | (first($previous_rows[] | select(.dataset_id == $probe.dataset_id)) // {}) as $old
      | cadence_days($entry.refresh_frequency) as $cadence
      | ($probe.last_modified // null) as $last_modified
      | (if ($probe | has("content_freshness_date")) then
           $probe.content_freshness_date
         elif ($probe.access_method // "" | ascii_downcase) == "camofox" then
           ($old.content_freshness_date // null)
         else null
         end) as $content_freshness_candidate
      | (if $content_freshness_candidate == null then null
         else (try (
           (($content_freshness_candidate + "T00:00:00Z") | fromdateiso8601) as $content_epoch
           | if $content_epoch <= $checked_epoch then $content_freshness_candidate else null end
         ) catch null)
         end) as $content_freshness_date
      | (if $last_modified == null then null
         else (($last_modified | fromdateiso8601) as $modified
           | ([0, (($checked_epoch - $modified) / 86400 | floor)] | max))
         end) as $last_modified_age
      | (if $content_freshness_date == null then null
         else ((($content_freshness_date + "T00:00:00Z") | fromdateiso8601) as $content_date
           | ([0, (($checked_epoch - $content_date) / 86400 | floor)] | max))
         end) as $content_freshness_age
      | ([$last_modified_age, $content_freshness_age] | map(select(. != null)) | min // null) as $staleness_days
      | (((($old.column_count | type) == "number"
            and ($probe.column_count | type) == "number"
            and $old.column_count != $probe.column_count)
          or (($old.first_row_hash | type) == "string"
            and ($probe.first_row_hash | type) == "string"
            and $old.first_row_hash != $probe.first_row_hash))) as $shape_changed
      | ($entry.expected_record_count // null) as $expected_record_count
      | (($probe.incomplete // false)
          or (($expected_record_count | type) == "number"
            and ($probe.record_count | type) == "number"
            and $probe.record_count < $expected_record_count)) as $incomplete
      | (($expected_record_count | type) == "number"
          and ($probe.record_count | type) == "number"
          and $probe.record_count >= ($expected_record_count * 0.5)) as $within_tolerance
      | ([$probe.http_status, $probe.last_modified, $probe.content_freshness_date,
          $probe.first_record_timestamp, $probe.snapshot_chars, $probe.record_count,
          $probe.timestamp, $probe.header_timestamp, $probe.newest_vehicle_timestamp]
          | any(. != null)) as $probe_measured
      | (if $staleness_days != null and $cadence != null then
           if $staleness_days <= ($cadence * 1.5) then "fresh"
           elif $staleness_days <= ($cadence * 3) then "aging"
           else "stale"
           end
         elif $staleness_days != null then "fresh"
         else "unknown-freshness"
         end) as $staleness_status
      | (if ($probe.access_method // "" | ascii_downcase) == "camofox" then
           "browser-dependent"
         elif (($probe.http_status | type) != "number" or $probe.http_status < 200 or $probe.http_status >= 300) then
           "unreachable"
         elif $probe.status == "degraded" then
           "degraded"
         elif $shape_changed
           or (($expected_record_count | type) == "number"
             and ($probe.record_count | type) == "number"
             and $probe.record_count < ($expected_record_count * 0.5)) then
           "degraded"
         elif $staleness_status == "stale" then "stale"
         elif $staleness_status == "aging" then "aging"
         elif $staleness_status == "unknown-freshness" then "unknown-freshness"
         else "fresh"
         end) as $status
      | {
          dataset_id: ($probe.dataset_id // null),
          last_checked: (if $probe_measured then $checked_at else null end),
          namespace: ($entry.namespace // null),
          url: ($probe.url // null),
          status: $status,
          message: ($probe.message // null),
          request_url: ($probe.request_url // null),
          access_method: ($probe.access_method // null),
          http_status: ($probe.http_status // null),
          content_length: ($probe.content_length // null),
          last_modified: $last_modified,
          content_freshness_date: $content_freshness_date,
          first_record_timestamp: ($probe.first_record_timestamp // null),
          wait_seconds: ($probe.wait_seconds // null),
          stations: ($probe.stations // null),
          timestamp: ($probe.timestamp // null),
          snapshot_chars: ($probe.snapshot_chars // null),
          record_count: ($probe.record_count // null),
          estimated_record_count: ($probe.estimated_record_count // null),
          record_count_estimated: ($probe.record_count_estimated // false),
          incomplete: $incomplete,
          column_count: ($probe.column_count // null),
          first_row_hash: ($probe.first_row_hash // null),
          content_shape_changed: $shape_changed,
          locations: ($probe.locations // null),
          date_range: ($probe.date_range // null),
          agency: ($probe.agency // null),
          stops: ($probe.stops // null),
          routes: ($probe.routes // null),
          trips: ($probe.trips // null),
          stop_times: ($probe.stop_times // null),
          calendar: ($probe.calendar // null),
          vehicle_count: ($probe.vehicle_count // null),
          header_timestamp: ($probe.header_timestamp // null),
          newest_vehicle_timestamp: ($probe.newest_vehicle_timestamp // null),
          expected_record_count: $expected_record_count,
          record_count_within_tolerance: $within_tolerance,
          staleness_days: $staleness_days,
          staleness_status: $staleness_status,
          access_dependency: (if ($probe.access_method // "" | ascii_downcase) == "camofox" then "browser" else "direct" end),
          freshness_signal: (if ($probe.dataset_id | startswith("gtfs_")) and $content_freshness_date != null then "content-date-parse"
                             elif $last_modified != null then "last-modified-header"
                             elif $content_freshness_date != null then "content-date-parse"
                             elif ($probe.access_method // "" | ascii_downcase) == "camofox" then "browser-only"
                             else "no-header" end),
          freshness_signal_source: (if ($probe.dataset_id | startswith("gtfs_")) and $content_freshness_date != null then "content_date_parse"
                                    elif $last_modified != null then "last_modified_header"
                                    elif $content_freshness_date != null then "content_date_parse"
                                    else "none" end)
        }
    )
  | map(
      . as $updated
      | (first($previous_rows[] | select(.dataset_id == $updated.dataset_id)) // {}) as $old
      | if $updated.last_checked == null and $old.last_checked != null then
          $updated + {last_checked: $old.last_checked}
        else $updated
        end
    ) as $updated_datasets
  | (if $due_mode then
       ([ $previous_rows[] | select(.dataset_id as $id | all($updated_datasets[]; .dataset_id != $id)) ] + $updated_datasets) as $merged
       | [ $manifest_rows[].id as $id | $merged[] | select(.dataset_id == $id) ]
     else $updated_datasets
     end) as $datasets
  | (reduce ["fresh", "aging", "stale", "degraded", "browser-dependent", "unreachable", "unknown", "unknown-freshness"][] as $status
      ({}; .[status_key($status)] = ([$datasets[] | select(.status == $status)] | length))) as $by_status
  | {
      schema: $schema,
      checked_at: $checked_at,
      _trust_summary: {
        checked_at: $checked_at,
        datasets_total: ($datasets | length),
        by_status: $by_status,
        datasets_health_signal_source: {
          last_modified_header: ([$datasets[] | select(.freshness_signal_source == "last_modified_header")] | length),
          content_date_parse: ([$datasets[] | select(.freshness_signal_source == "content_date_parse")] | length),
          neither: ([$datasets[] | select(.freshness_signal_source == "none")] | length)
        },
        datasets_with_no_last_modified_header: ([$datasets[] | select(.last_modified == null)] | length),
        datasets_with_no_record_count_extracted: ([$datasets[] | select(.record_count == null)] | length),
        oldest_last_modified: ([$datasets[].last_modified | select(. != null)] | min // null),
        newest_last_modified: ([$datasets[].last_modified | select(. != null)] | max // null),
        stale_datasets: ([$datasets[]
          | select(.status == "stale")
          | {dataset_id, days_since_modified: .staleness_days}]
          | sort_by(.days_since_modified // -1)
          | reverse)
      },
      datasets: $datasets
    }
  ' "$results_file"
