#!/usr/bin/env bash
# Dataset failures are data: record them and continue so the summary is complete.

manifest="${1:-datapulse.json}"

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
headers_file="$(mktemp)"
previous_file="$(mktemp)"
trap 'rm -f "$results_file" "$body_file" "$headers_file" "$previous_file"' EXIT

if [[ -s health/latest.json ]]; then
  cp health/latest.json "$previous_file"
elif command -v git >/dev/null 2>&1; then
  git show HEAD:health/latest.json > "$previous_file" 2>/dev/null || true
fi

curl_timeout="${DATAPULSE_CURL_TIMEOUT:-30}"
camofox_timeout="${CAMOFOX_TIMEOUT:-30}"
camofox_base_url="${CAMOFOX_BASE_URL:-http://100.74.84.121:9377}"

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
  local stations timestamp snapshot_chars

  if ! open_response="$(curl --location --silent --show-error --fail \
    --max-time "$camofox_timeout" \
    --request POST "${camofox_base_url}/tabs/open" \
    --header 'Content-Type: application/json' \
    --data "$(jq -cn --arg userId "$user_id" --arg url "$source_url" \
      '{userId: $userId, url: $url}')" 2>/dev/null)"; then
    sleep 6
    if ! open_response="$(curl --location --silent --show-error --fail \
      --max-time "$camofox_timeout" \
      --request POST "${camofox_base_url}/tabs/open" \
      --header 'Content-Type: application/json' \
      --data "$(jq -cn --arg userId "$user_id" --arg url "$source_url" \
        '{userId: $userId, url: $url}')" 2>/dev/null)"; then
      details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
      emit "$dataset_id" "$source_url" "unreachable" \
        "Camofox unavailable; browser check required" "$details"
      return 0
    fi
  fi

  tab_id="$(jq -r '.tabId // empty' <<< "$open_response" 2>/dev/null)"
  if [[ -z "$tab_id" ]]; then
    details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
    emit "$dataset_id" "$source_url" "unreachable" "Camofox returned no tab id" "$details"
    return 0
  fi

  sleep "$wait_seconds"

  if ! snapshot_response="$(curl --location --silent --show-error --fail \
    --max-time "$camofox_timeout" \
    "${camofox_base_url}/tabs/${tab_id}/snapshot?userId=${user_id}" 2>/dev/null)"; then
    sleep 6
    if ! snapshot_response="$(curl --location --silent --show-error --fail \
      --max-time "$camofox_timeout" \
      "${camofox_base_url}/tabs/${tab_id}/snapshot?userId=${user_id}" 2>/dev/null)"; then
      close_camofox_tab "$tab_id" "$user_id" || true
      details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
      emit "$dataset_id" "$source_url" "unreachable" "Camofox snapshot failed" "$details"
      return 0
    fi
  fi

  snapshot="$(jq -r '.snapshot // empty' <<< "$snapshot_response" 2>/dev/null)"
  if [[ -z "$snapshot" ]]; then
    close_camofox_tab "$tab_id" "$user_id" || true
    details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
    emit "$dataset_id" "$source_url" "unreachable" "Camofox returned no snapshot" "$details"
    return 0
  fi

  stations="$(grep -Ec 'row "[0-9]+ [A-Z]' <<< "$snapshot" || true)"
  timestamp="$(grep -Eo '[0-9]{2}/[0-9]{2}/[0-9]{4}, [0-9]{2}:[0-9]{2}' \
    <<< "$snapshot" | head -n 1 || true)"
  snapshot_chars="${#snapshot}"

  if ! close_camofox_tab "$tab_id" "$user_id"; then
    details="$(jq -cn \
      --arg access_method 'Camofox' \
      --argjson wait_seconds "$wait_seconds" \
      '{access_method: $access_method, wait_seconds: $wait_seconds}')"
    emit "$dataset_id" "$source_url" "unreachable" "Camofox tab close failed" "$details"
    return 0
  fi

  details="$(jq -cn \
    --arg access_method 'Camofox' \
    --argjson wait_seconds "$wait_seconds" \
    --argjson stations "$stations" \
    --arg timestamp "$timestamp" \
    --argjson snapshot_chars "$snapshot_chars" \
    '{
      access_method: $access_method,
      wait_seconds: $wait_seconds,
      stations: $stations,
      timestamp: (if $timestamp == "" then null else $timestamp end),
      snapshot_chars: $snapshot_chars
    }')"
  emit "$dataset_id" "$source_url" "browser-dependent" "Browser check succeeded" "$details"
}

check_head_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local http_status status content_length last_modified details

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

  details="$(jq -cn \
    --arg access_method 'direct curl HEAD' \
    --argjson http_status "$http_status" \
    --argjson content_length "$content_length" \
    --arg last_modified "$last_modified" \
    '{
      access_method: $access_method,
      http_status: $http_status,
      content_length: $content_length,
      last_modified: (if $last_modified == "" then null else $last_modified end)
    }')"
  emit "$dataset_id" "$source_url" "fresh" "HTTP ${http_status}" "$details"
}

check_weather_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local http_status content_length record_count locations date_start date_end details
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
    '{
      request_url: $request_url,
      access_method: "direct curl GET",
      http_status: $http_status,
      content_length: $content_length,
      record_count: $record_count,
      column_count: $column_count,
      first_row_hash: $first_row_hash,
      locations: $locations,
      date_range: {start: ($date_start // null), end: ($date_end // null)}
    }')"
  emit "$dataset_id" "$source_url" "fresh" "HTTP ${http_status}" "$details"
}

check_direct_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local request_url="$source_url"
  local http_status content_length first_record_timestamp details
  local record_count column_count first_row_hash first_row

  if [[ "$dataset_id" == "fuelprice" ]]; then
    request_url="https://api.data.gov.my/data-catalogue?id=fuelprice&limit=1"
  fi

  if ! http_status="$(curl --location --silent --show-error \
    --max-time "$curl_timeout" \
    --output "$body_file" --write-out '%{http_code}' "$request_url" 2>/dev/null)"; then
    details="$(jq -cn --arg request_url "$request_url" \
      '{request_url: $request_url, access_method: "direct curl GET"}')"
    emit "$dataset_id" "$source_url" "unreachable" "curl request failed" "$details"
    return 0
  fi

  if [[ ! "$http_status" =~ ^2[0-9][0-9]$ ]]; then
    emit_http_failure "$dataset_id" "$source_url" "$request_url" "$http_status"
    return 0
  fi

  content_length="$(wc -c < "$body_file" | tr -d '[:space:]')"
  record_count="$(jq 'if type == "array" then length else null end' "$body_file" 2>/dev/null || printf 'null')"
  column_count="$(jq 'if type == "array" then .[0] else . end | if type == "object" then (keys | length) else null end' "$body_file" 2>/dev/null || printf 'null')"
  first_row="$(jq -cS 'if type == "array" then .[0] else . end' "$body_file" 2>/dev/null || true)"
  if [[ -n "$first_row" ]]; then
    first_row_hash="$(printf '%s' "$first_row" | sha256sum | awk '{print $1}')"
  else
    first_row_hash=""
  fi
  first_record_timestamp="$(
    jq -r 'if type == "array" then .[0] else . end
      | .timestamp // .date // .publish_date // empty' "$body_file" 2>/dev/null || true
  )"
  details="$(jq -cn \
    --arg request_url "$request_url" \
    --argjson http_status "$http_status" \
    --argjson content_length "$content_length" \
    --argjson record_count "$record_count" \
    --argjson column_count "$column_count" \
    --arg first_row_hash "$first_row_hash" \
    --arg first_record_timestamp "$first_record_timestamp" \
    '{
      request_url: $request_url,
      access_method: "direct curl GET",
      http_status: $http_status,
      content_length: $content_length,
      record_count: $record_count,
      column_count: $column_count,
      first_row_hash: (if $first_row_hash == "" then null else $first_row_hash end),
      first_record_timestamp: (
        if $first_record_timestamp == "" then null else $first_record_timestamp end
      )
    }')"
  emit "$dataset_id" "$source_url" "fresh" "HTTP ${http_status}" "$details"
}

warm_camofox_browser

while IFS=$'\t' read -r dataset_id source_url; do
  case "$dataset_id" in
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
      check_head_dataset "$dataset_id" "$source_url"
      ;;
    met_weather)
      check_weather_dataset "$dataset_id" "$source_url"
      ;;
    *)
      check_direct_dataset "$dataset_id" "$source_url"
      ;;
  esac
done < <(jq -r '.datasets[] | [.id, .url] | @tsv' "$manifest")

expected_count="$(jq '.datasets | length' "$manifest")"
actual_count="$(wc -l < "$results_file" | tr -d '[:space:]')"
if [[ "$actual_count" != "$expected_count" ]]; then
  printf 'Internal error: expected %s results, wrote %s\n' "$expected_count" "$actual_count" >&2
  exit 1
fi

checked_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
checked_epoch="$(date -u -d "$checked_at" +%s)"
jq -s \
  --slurpfile manifest "$manifest" \
  --slurpfile previous "$previous_file" \
  --arg schema "datapulse/v0.2/dataset-health" \
  --arg checked_at "$checked_at" \
  --argjson checked_epoch "$checked_epoch" \
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
    if $status == "browser-dependent" then "browser_dependent" else $status end;

  ($manifest[0].datasets // []) as $manifest_rows
  | ((($previous[0] // {}).datasets) // []) as $previous_rows
  | map(
      . as $probe
      | ($manifest_rows[] | select(.id == $probe.dataset_id)) as $entry
      | (first($previous_rows[] | select(.dataset_id == $probe.dataset_id)) // {}) as $old
      | cadence_days($entry.refresh_frequency) as $cadence
      | ($probe.last_modified // null) as $last_modified
      | (if $last_modified == null then null
         else (($last_modified | fromdateiso8601) as $modified
           | ([0, (($checked_epoch - $modified) / 86400 | floor)] | max))
         end) as $staleness_days
      | (($old.content_length | type) == "number"
          and ($probe.content_length | type) == "number"
          and $old.content_length == $probe.content_length) as $content_length_stable
      | (((($old.column_count | type) == "number"
            and ($probe.column_count | type) == "number"
            and $old.column_count != $probe.column_count)
          or (($old.first_row_hash | type) == "string"
            and ($probe.first_row_hash | type) == "string"
            and $old.first_row_hash != $probe.first_row_hash))) as $shape_changed
      | ($entry.expected_record_count // null) as $expected_record_count
      | (($expected_record_count | type) == "number"
          and ($probe.record_count | type) == "number"
          and $probe.record_count >= ($expected_record_count * 0.5)) as $within_tolerance
      | (if $last_modified != null and $cadence != null then
           if $staleness_days <= ($cadence * 1.5) then "fresh"
           elif $staleness_days <= ($cadence * 3) then "aging"
           else "stale"
           end
         elif $last_modified == null and $cadence != null then
           if $content_length_stable then "aging" else "stale" end
         elif $last_modified != null then "fresh"
         else "unknown"
         end) as $staleness_status
      | (if ($probe.access_method // "" | ascii_downcase) == "camofox" then
           if $probe.status == "browser-dependent" then "browser-dependent" else "unreachable" end
         elif (($probe.http_status | type) != "number" or $probe.http_status < 200 or $probe.http_status >= 300) then
           "unreachable"
         elif $shape_changed
           or (($expected_record_count | type) == "number"
             and ($probe.record_count | type) == "number"
             and $probe.record_count < ($expected_record_count * 0.5)) then
           "degraded"
         elif $staleness_status == "stale" then "stale"
         elif $staleness_status == "aging" then "aging"
         else "fresh"
         end) as $status
      | {
          dataset_id: ($probe.dataset_id // null),
          url: ($probe.url // null),
          status: $status,
          message: ($probe.message // null),
          request_url: ($probe.request_url // null),
          access_method: ($probe.access_method // null),
          http_status: ($probe.http_status // null),
          content_length: ($probe.content_length // null),
          last_modified: $last_modified,
          first_record_timestamp: ($probe.first_record_timestamp // null),
          wait_seconds: ($probe.wait_seconds // null),
          stations: ($probe.stations // null),
          timestamp: ($probe.timestamp // null),
          snapshot_chars: ($probe.snapshot_chars // null),
          record_count: ($probe.record_count // null),
          column_count: ($probe.column_count // null),
          first_row_hash: ($probe.first_row_hash // null),
          content_shape_changed: $shape_changed,
          locations: ($probe.locations // null),
          date_range: ($probe.date_range // null),
          expected_record_count: $expected_record_count,
          record_count_within_tolerance: $within_tolerance,
          staleness_days: $staleness_days,
          staleness_status: $staleness_status,
          access_dependency: (if ($probe.access_method // "" | ascii_downcase) == "camofox" then "browser" else "direct" end),
          freshness_signal: (if ($probe.access_method // "" | ascii_downcase) == "camofox" then "browser-only"
                             elif $last_modified == null then "no-header"
                             else "last-modified-header" end)
        }
    ) as $datasets
  | (reduce ["fresh", "aging", "stale", "degraded", "browser-dependent", "unreachable", "unknown"][] as $status
      ({}; .[status_key($status)] = ([$datasets[] | select(.status == $status)] | length))) as $by_status
  | {
      schema: $schema,
      checked_at: $checked_at,
      _trust_summary: {
        checked_at: $checked_at,
        datasets_total: ($datasets | length),
        by_status: $by_status,
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
