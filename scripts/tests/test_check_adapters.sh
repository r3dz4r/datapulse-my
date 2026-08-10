#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture="$(mktemp)"
invalid_policy="$(mktemp)"
trap 'rm -f "$fixture" "$invalid_policy"' EXIT

DATAPULSE_CHECK_SOURCE_ONLY=true source "$repo_root/scripts/check.sh"

[[ "$(probe_adapter fuelprice)" == "direct" ]]
[[ "$(probe_adapter met_weather)" == "weather" ]]
[[ "$(probe_adapter doe_apims)" == "browser" ]]
[[ "$(probe_adapter gtfs_realtime_ktmb)" == "gtfs-realtime" ]]
[[ "$(probe_adapter hansard_sittings)" == "hansard-script" ]]
[[ "$(probe_policy_value met_weather '.freshness["extraction-mode"]')" == "min" ]]
[[ "$(probe_policy_value exchangerates_daily_0900 '.rolling["fingerprint-mode"]')" == "columns-only" ]]
[[ "$(probe_policy_value doe_apims '.browser["wait-seconds"]')" == "30" ]]

today="$(date -u +'%Y-%m-%d')"
yesterday="$(date -u -d 'yesterday' +'%Y-%m-%d')"
tomorrow="$(date -u -d 'tomorrow' +'%Y-%m-%d')"
jq -cn --arg yesterday "$yesterday" --arg today "$today" --arg tomorrow "$tomorrow" \
  '[{date:$yesterday},{date:$today},{date:$tomorrow}]' > "$fixture"
[[ "$(extract_max_date "$fixture" date)" == "$today" ]]
[[ "$(extract_min_date "$fixture" date)" == "$yesterday" ]]
[[ "$(DATAPULSE_CONTENT_FILE="$fixture" "$repo_root/scripts/extract_content_freshness.sh" ignored met_weather)" == "$yesterday" ]]

printf '%s\n' 'Updated 2026-08-07; previous 01/08/2026' > "$fixture"
browser_pattern="$(probe_policy_value doe_apims '.browser["date-pattern"]')"
[[ "$(extract_browser_dates "$fixture" "$browser_pattern")" == "2026-08-07" ]]

printf '%s\n' '{"version":1,"defaults":{"adapter":"direct","freshness-fallback":"last-modified"},"datasets":{"broken":{"adapter":"browser"}}}' > "$invalid_policy"
probe_policy="$invalid_policy"
if validate_adapter_config broken browser 2>/dev/null; then
  printf 'browser adapter unexpectedly accepted missing configuration\n' >&2
  exit 1
fi

probe_policy="$repo_root/scripts/probe-policy.json"
check_direct_dataset() { printf 'direct:%s\n' "$1"; }
check_weather_dataset() { printf 'weather:%s\n' "$1"; }
check_browser_dataset() { printf 'browser:%s:%s\n' "$1" "$3"; }
check_gtfs_dataset() { printf 'gtfs:%s\n' "$1"; }
check_hansard_script_dataset() { printf 'hansard:%s\n' "$1"; }

[[ "$(dispatch_policy_adapter fuelprice https://example.invalid)" == "direct:fuelprice" ]]
[[ "$(dispatch_policy_adapter met_weather https://example.invalid)" == "weather:met_weather" ]]
[[ "$(dispatch_policy_adapter doe_apims https://example.invalid)" == "browser:doe_apims:30" ]]
[[ "$(dispatch_policy_adapter gtfs_realtime_ktmb https://example.invalid)" == "gtfs:gtfs_realtime_ktmb" ]]
[[ "$(dispatch_policy_adapter hansard_sittings https://example.invalid)" == "hansard:hansard_sittings" ]]

printf '%s\n' '{"status":"ok","katalog":{"dewan-rakyat":{"http_status":200,"sittings_total":4086,"latest":"2026-07-16"},"dewan-negara":{"http_status":200,"sittings_total":1522,"latest":"2026-08-04"},"kamar-khas":{"http_status":200,"sittings_total":584,"latest":"2026-07-16"}},"takwim":{"current_term_end":"2026-08-04","total_terms":15},"mps":{"http_status":200,"total_mps":2017},"freshness":{"content_freshness_date":"2026-08-04"}}' > "$fixture"
[[ "$(extract_hansard_probe_metrics hansard_sittings "$fixture")" == '{"http_status":200,"record_count":6192,"content_freshness_date":"2026-08-04"}' ]]
[[ "$(extract_hansard_probe_metrics hansard_parliamentary_terms "$fixture")" == '{"http_status":200,"record_count":15,"content_freshness_date":"2026-08-04"}' ]]
[[ "$(extract_hansard_probe_metrics hansard_mps "$fixture")" == '{"http_status":200,"record_count":2017,"content_freshness_date":"2026-08-04"}' ]]
jq '.mps.last_modified = "2026-08-09T12:34:56Z"' "$fixture" > "$invalid_policy"
[[ "$(extract_hansard_probe_metrics hansard_mps "$invalid_policy")" == '{"http_status":200,"record_count":2017,"content_freshness_date":"2026-08-09"}' ]]

[[ "$(render_dynamic_url pricecatcher 2025-12-31)" == "https://storage.data.gov.my/pricecatcher/pricecatcher_2025-12.parquet" ]]
[[ "$(render_dynamic_url pricecatcher 2026-01-01)" == "https://storage.data.gov.my/pricecatcher/pricecatcher_2026-01.parquet" ]]
[[ "$(render_dynamic_url ridership_od_komuter 2025-12-31)" == "https://storage.data.gov.my/transportation/ktmb/komuter_2025.csv" ]]
[[ "$(render_dynamic_url ridership_od_komuter 2026-01-01)" == "https://storage.data.gov.my/transportation/ktmb/komuter_2026.csv" ]]
[[ "$(render_dynamic_url registration_transactions_all 2027-01-01)" == "https://storage.data.gov.my/transportation/vehicles_2027.csv" ]]
[[ "$(render_dynamic_url registration_transactions_car 2027-01-01)" == "https://storage.data.gov.my/transportation/cars_2027.csv" ]]
[[ "$(render_dynamic_url registration_transactions_motorcycle 2027-01-01)" == "https://storage.data.gov.my/transportation/motorcycles_2027.csv" ]]
[[ "$(render_dynamic_url ridership_od_brt_daily 2027-01-01)" == "https://storage.data.gov.my/transportation/bus/brt_2027_daily.csv" ]]
[[ "$(render_dynamic_url ridership_od_rapidrail_daily 2027-01-01)" == "https://storage.data.gov.my/transportation/rail/rapidrail_2027_daily.csv" ]]

printf '%s\n' '{"version":1,"defaults":{"adapter":"direct","freshness-fallback":"last-modified"},"datasets":{"pricecatcher":{"dynamic-url":{"template":"http://example.invalid/{YYYY-MM}"}}}}' > "$invalid_policy"
probe_policy="$invalid_policy"
if render_dynamic_url pricecatcher 2026-01-01 >/dev/null 2>&1; then
  printf 'unsafe dynamic URL template unexpectedly rendered\n' >&2
  exit 1
fi
probe_policy="$repo_root/scripts/probe-policy.json"

check_npra_guidance_dataset() { printf 'guidance:%s\n' "$1"; }
[[ "$(dispatch_dataset npra_drug_registration_guidance https://example.invalid "$fixture")" == "guidance:npra_drug_registration_guidance" ]]
[[ "$(dispatch_dataset npra_products_registered https://example.invalid "$fixture")" == "direct:npra_products_registered" ]]
[[ "$(probe_policy_value npra_products_registered '.["special-validator"]')" == "npra-registration-format" ]]
[[ "$(probe_policy_value npra_drug_registration_guidance '.["special-validator"]')" == "npra-guidance-appendices" ]]

if declare -F check_head_dataset >/dev/null; then
  printf 'dead check_head_dataset helper still exists\n' >&2
  exit 1
fi

printf 'Probe adapter tests passed.\n'
