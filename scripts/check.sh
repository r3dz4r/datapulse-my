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
trap 'rm -f "$results_file" "$body_file" "$headers_file"' EXIT

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
    2??) printf 'healthy' ;;
    4??) printf 'down' ;;
    5??) printf 'degraded' ;;
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
    details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
    emit "$dataset_id" "$source_url" "browser-required" \
      "Camofox unavailable; browser check required" "$details"
    return 0
  fi

  tab_id="$(jq -r '.tabId // empty' <<< "$open_response" 2>/dev/null)"
  if [[ -z "$tab_id" ]]; then
    details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
    emit "$dataset_id" "$source_url" "error" "Camofox returned no tab id" "$details"
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
      emit "$dataset_id" "$source_url" "error" "Camofox snapshot failed" "$details"
      return 0
    fi
  fi

  snapshot="$(jq -r '.snapshot // empty' <<< "$snapshot_response" 2>/dev/null)"
  if [[ -z "$snapshot" ]]; then
    close_camofox_tab "$tab_id" "$user_id" || true
    details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
    emit "$dataset_id" "$source_url" "error" "Camofox returned no snapshot" "$details"
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
    emit "$dataset_id" "$source_url" "error" "Camofox tab close failed" "$details"
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
  emit "$dataset_id" "$source_url" "healthy" "Browser check succeeded" "$details"
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
    emit "$dataset_id" "$source_url" "error" "curl HEAD request failed" "$details"
    return 0
  fi

  status="$(http_status_name "$http_status")"
  if [[ "$status" != "healthy" ]]; then
    emit_http_failure "$dataset_id" "$source_url" "$source_url" "$http_status" \
      "direct curl HEAD"
    return 0
  fi

  content_length="$(awk 'BEGIN { IGNORECASE=1 } /^content-length:/ { value=$2 } END { gsub("\\r", "", value); print value }' "$headers_file")"
  last_modified="$(awk 'BEGIN { IGNORECASE=1 } /^last-modified:/ { sub(/^[^:]+:[[:space:]]*/, ""); value=$0 } END { gsub("\\r", "", value); print value }' "$headers_file")"

  if [[ ! "$content_length" =~ ^[0-9]+$ || -z "$last_modified" ]]; then
    details="$(jq -cn \
      --arg access_method 'direct curl HEAD' \
      --argjson http_status "$http_status" \
      '{access_method: $access_method, http_status: $http_status}')"
    emit "$dataset_id" "$source_url" "error" "Missing expected response headers" "$details"
    return 0
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
      last_modified: $last_modified
    }')"
  emit "$dataset_id" "$source_url" "healthy" "HTTP ${http_status}" "$details"
}

check_weather_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local http_status content_length record_count locations date_start date_end details

  if ! http_status="$(curl --location --silent --show-error \
    --max-time "$curl_timeout" \
    --output "$body_file" --write-out '%{http_code}' "$source_url" 2>/dev/null)"; then
    emit "$dataset_id" "$source_url" "error" "curl request failed" \
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
    emit "$dataset_id" "$source_url" "error" "Response was not a JSON array" "$details"
    return 0
  fi

  content_length="$(wc -c < "$body_file" | tr -d '[:space:]')"
  record_count="$(jq 'length' "$body_file")"
  locations="$(jq '[.[].location.location_id] | unique | length' "$body_file")"
  date_start="$(jq -r '[.[].date] | min // empty' "$body_file")"
  date_end="$(jq -r '[.[].date] | max // empty' "$body_file")"
  details="$(jq -cn \
    --arg request_url "$source_url" \
    --argjson http_status "$http_status" \
    --argjson content_length "$content_length" \
    --argjson record_count "$record_count" \
    --argjson locations "$locations" \
    --arg date_start "$date_start" \
    --arg date_end "$date_end" \
    '{
      request_url: $request_url,
      access_method: "direct curl GET",
      http_status: $http_status,
      content_length: $content_length,
      record_count: $record_count,
      locations: $locations,
      date_range: {start: ($date_start // null), end: ($date_end // null)}
    }')"
  emit "$dataset_id" "$source_url" "healthy" "HTTP ${http_status}" "$details"
}

check_direct_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local request_url="$source_url"
  local http_status content_length first_record_timestamp details

  if [[ "$dataset_id" == "fuelprice" ]]; then
    request_url="https://api.data.gov.my/data-catalogue?id=fuelprice&limit=1"
  fi

  if ! http_status="$(curl --location --silent --show-error \
    --max-time "$curl_timeout" \
    --output "$body_file" --write-out '%{http_code}' "$request_url" 2>/dev/null)"; then
    details="$(jq -cn --arg request_url "$request_url" \
      '{request_url: $request_url, access_method: "direct curl GET"}')"
    emit "$dataset_id" "$source_url" "error" "curl request failed" "$details"
    return 0
  fi

  if [[ ! "$http_status" =~ ^2[0-9][0-9]$ ]]; then
    emit_http_failure "$dataset_id" "$source_url" "$request_url" "$http_status"
    return 0
  fi

  content_length="$(wc -c < "$body_file" | tr -d '[:space:]')"
  first_record_timestamp="$(
    jq -r 'if type == "array" then .[0] else . end
      | .timestamp // .date // .publish_date // empty' "$body_file" 2>/dev/null || true
  )"
  details="$(jq -cn \
    --arg request_url "$request_url" \
    --argjson http_status "$http_status" \
    --argjson content_length "$content_length" \
    --arg first_record_timestamp "$first_record_timestamp" \
    '{
      request_url: $request_url,
      access_method: "direct curl GET",
      http_status: $http_status,
      content_length: $content_length,
      first_record_timestamp: (
        if $first_record_timestamp == "" then null else $first_record_timestamp end
      )
    }')"
  emit "$dataset_id" "$source_url" "healthy" "HTTP ${http_status}" "$details"
}

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
    dgm_crops_state|dgm_schools_district|dosm_birth_state|dosm_death_state|\
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

jq -s \
  --arg schema "datapulse/v0.1/dataset-health" \
  --arg checked_at "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
  '{
    schema: $schema,
    checked_at: $checked_at,
    datasets: map({
      dataset_id: (.dataset_id // null),
      url: (.url // null),
      status: (.status // "unknown"),
      message: (.message // null),
      request_url: (.request_url // null),
      access_method: (.access_method // null),
      http_status: (.http_status // null),
      content_length: (.content_length // null),
      last_modified: (.last_modified // null),
      first_record_timestamp: (.first_record_timestamp // null),
      wait_seconds: (.wait_seconds // null),
      stations: (.stations // null),
      timestamp: (.timestamp // null),
      snapshot_chars: (.snapshot_chars // null),
      record_count: (.record_count // null),
      locations: (.locations // null),
      date_range: (.date_range // null)
    })
  }' "$results_file"
