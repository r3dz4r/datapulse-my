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
[[ "$(probe_policy_value met_weather '.freshness["extraction-mode"]')" == "min" ]]
[[ "$(probe_policy_value exchangerates_daily_0900 '.rolling["fingerprint-mode"]')" == "columns-only" ]]
[[ "$(probe_policy_value doe_apims '.browser["wait-seconds"]')" == "30" ]]

printf '%s\n' '[{"date":"2026-08-08"},{"date":"2026-08-14"}]' > "$fixture"
[[ "$(extract_max_date "$fixture" date)" == "2026-08-14" ]]
[[ "$(extract_min_date "$fixture" date)" == "2026-08-08" ]]
[[ "$(DATAPULSE_CONTENT_FILE="$fixture" "$repo_root/scripts/extract_content_freshness.sh" ignored met_weather)" == "2026-08-08" ]]

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

[[ "$(dispatch_policy_adapter fuelprice https://example.invalid)" == "direct:fuelprice" ]]
[[ "$(dispatch_policy_adapter met_weather https://example.invalid)" == "weather:met_weather" ]]
[[ "$(dispatch_policy_adapter doe_apims https://example.invalid)" == "browser:doe_apims:30" ]]
[[ "$(dispatch_policy_adapter gtfs_realtime_ktmb https://example.invalid)" == "gtfs:gtfs_realtime_ktmb" ]]

printf 'Probe adapter tests passed.\n'
