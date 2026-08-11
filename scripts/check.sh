#!/usr/bin/env bash
# Dataset failures are data: record them and continue so the summary is complete.

due_mode=false
compare_health=false
tier_filter=""
cadence_override=""
manifest="datapulse.json"

usage() {
  printf 'Usage: %s [--compare-health] [--due [--tier <name>] [--cadence-minutes <n>]] [manifest]\n' "$0" >&2
}

while (( $# > 0 )); do
  case "$1" in
    --due)
      due_mode=true
      shift
      ;;
    --compare-health)
      compare_health=true
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
probe_policy="${DATAPULSE_PROBE_POLICY:-$script_dir/probe-policy.json}"

if ! command -v jq >/dev/null 2>&1; then
  printf 'jq is required\n' >&2
  exit 1
fi

if [[ ! -r "$probe_policy" ]] || ! jq -e '
  .version == 1
  and (.defaults.adapter | type == "string")
  and (.datasets | type == "object")
  and ((.templates // {}) | type == "object")
  and (. as $policy
    | all(.datasets[];
        (.template // "") as $template
        | $template == "" or (($policy.templates // {}) | has($template))))
' "$probe_policy" >/dev/null 2>&1; then
  printf 'Invalid probe policy: %s\n' "$probe_policy" >&2
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
comparison_output_file="$(mktemp)"
probe_results_dir="$(mktemp -d)"
trap 'rm -f "$results_file" "$body_file" "$content_body_file" "$headers_file" "$previous_file" "$selected_manifest_file" "$comparison_output_file"; rm -rf "$probe_results_dir"' EXIT

if [[ -s health/latest.json ]]; then
  cp health/latest.json "$previous_file"
elif command -v git >/dev/null 2>&1; then
  git show HEAD:health/latest.json > "$previous_file" 2>/dev/null || true
fi

if $due_mode; then
  retry_cadence_minutes="${RETRY_CADENCE_MINUTES:-240}"
  if [[ ! "$retry_cadence_minutes" =~ ^[1-9][0-9]*$ ]]; then
    printf 'Invalid retry cadence minutes: %s\n' "$retry_cadence_minutes" >&2
    exit 2
  fi
  now_epoch="$(date -u +%s)"
  jq \
    --slurpfile previous "$previous_file" \
    --arg tier_filter "$tier_filter" \
    --arg cadence_override "$cadence_override" \
    --argjson retry_cadence_minutes "$retry_cadence_minutes" \
    --argjson now_epoch "$now_epoch" \
    '
    def tier_and_cadence($frequency):
      ($frequency // "" | ascii_downcase) as $frequency
      | if $frequency == "30 seconds" or $frequency == "hourly" then ["realtime", 15]
        elif $frequency | startswith("daily (weekdays") then ["daily", 60]
        elif $frequency == "daily" then ["daily", 1440]
        elif $frequency == "weekly" or $frequency == "monthly" or $frequency == "quarterly" then ["weekly-monthly", 10080]
        elif $frequency == "annual" or $frequency == "biennial to triennial (survey years)" or $frequency == "as-required" then ["slow", 43200]
        else error("Unsupported refresh_frequency: \($frequency)")
        end;

    def failure_cadence($status; $message; $default_minutes):
      if (($status == "browser-dependent" and (($message // "") | test("unavailable|failed|error"; "i")))
          or $status == "unreachable" or $status == "degraded")
      then $retry_cadence_minutes
      else $default_minutes
      end;

    ((($previous[0] // {}).datasets) // []) as $previous_rows
    | .datasets |= map(
        . as $entry
        | tier_and_cadence($entry.refresh_frequency) as $schedule
        | (first($previous_rows[] | select(.dataset_id == $entry.id)) // {}) as $old
        | (if $cadence_override == "" then $schedule[1] else ($cadence_override | tonumber) end) as $cadence_minutes
        | failure_cadence($old.status; $old.message; $cadence_minutes) as $effective_cadence
        | (try ($old.last_checked | fromdateiso8601) catch null) as $last_checked_epoch
        | select(($tier_filter == "" or $schedule[0] == $tier_filter)
            and ($last_checked_epoch == null or ($now_epoch - $last_checked_epoch) >= ($effective_cadence * 60)))
      )
    ' "$manifest" > "$selected_manifest_file"
else
  cp "$manifest" "$selected_manifest_file"
fi

curl_timeout="${DATAPULSE_CURL_TIMEOUT:-30}"
gtfs_timeout="${DATAPULSE_GTFS_TIMEOUT:-45}"
camofox_timeout="${CAMOFOX_TIMEOUT:-45}"
camofox_base_url="${CAMOFOX_BASE_URL:-http://localhost:9377}"

probe_policy_value() {
  local dataset_id="$1"
  local filter="$2"

  jq -er --arg id "$dataset_id" \
    "(. as \$policy
      | (\$policy.datasets[\$id] // {}) as \$dataset
      | (\$dataset.template // \"\") as \$template
      | (((\$policy.templates // {})[\$template] // {})
        * \$dataset))${filter} // empty" \
    "$probe_policy"
}

probe_policy_headers() {
  local dataset_id="$1"

  jq -r --arg id "$dataset_id" '
    . as $policy
    | ($policy.datasets[$id] // {}) as $dataset
    | ($dataset.template // "") as $template
    | (((($policy.templates // {})[$template] // {}) * $dataset).headers // {})
    | to_entries[]
    | [.key, .value]
    | @tsv
  ' "$probe_policy"
}

respect_robots_txt() {
  local dataset_id="$1"
  local url="$2"
  local ua="${DATAPULSE_USER_AGENT:-DataPulseMY/1.0 (+https://data-pulse.my/about)}"
  local origin robots_url robots_body

  origin="$(printf '%s' "$url" | awk -F/ '{print $1"//"$3}')"
  if [[ ! "$origin" =~ ^[A-Za-z][A-Za-z0-9+.-]*://[^/]+$ ]]; then
    printf 'robots.txt check skipped: %s has malformed URL %s\n' \
      "$dataset_id" "$url" >&2
    return 0
  fi

  robots_url="${origin}/robots.txt"
  robots_body="$(curl --location --silent --show-error --max-time 5 \
    --output - "$robots_url" 2>/dev/null)" || return 0
  [[ -n "$robots_body" ]] || return 0

  if printf '%s' "$robots_body" | awk -v ua="$ua" '
    BEGIN {
      blocked=0
      ua_token=tolower(ua)
      sub(/[[:space:]].*/, "", ua_token)
      ua_product=ua_token
      sub(/\/.*/, "", ua_product)
      matching=0
    }
    {
      sub(/\r$/, "")
      sub(/[[:space:]]*#.*/, "")
    }
    tolower($0) ~ /^[[:space:]]*user-agent[[:space:]]*:/ {
      value=$0
      sub(/^[^:]*:[[:space:]]*/, "", value)
      sub(/[[:space:]]*$/, "", value)
      value=tolower(value)
      matching=(value == "*" || value == ua_product || value == ua_token || value == tolower(ua))
      next
    }
    tolower($0) ~ /^[[:space:]]*disallow[[:space:]]*:/ {
      path=$0
      sub(/^[^:]*:[[:space:]]*/, "", path)
      sub(/[[:space:]]*$/, "", path)
      if (matching && path == "/") blocked=1
    }
    END { exit blocked ? 0 : 1 }
  ' >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

probe_adapter() {
  local dataset_id="$1"

  jq -er --arg id "$dataset_id" '
    . as $policy
    | ($policy.datasets[$id] // {}) as $dataset
    | ($dataset.template // "") as $template
    | (((($policy.templates // {})[$template] // {}) * $dataset).adapter
      // $policy.defaults.adapter)
  ' "$probe_policy"
}

validate_adapter_config() {
  local dataset_id="$1"
  local adapter="$2"

  case "$adapter" in
    direct|gtfs-static|gtfs-realtime|hansard-script)
      ;;
    weather)
      probe_policy_value "$dataset_id" '.freshness["content-date-field"]' >/dev/null \
        && probe_policy_value "$dataset_id" '.freshness["extraction-mode"]' >/dev/null \
        || { printf 'Probe policy error: %s weather adapter requires freshness configuration\n' "$dataset_id" >&2; return 1; }
      ;;
    browser)
      probe_policy_value "$dataset_id" '.browser["date-pattern"]' >/dev/null \
        && probe_policy_value "$dataset_id" '.browser["wait-seconds"]' >/dev/null \
        || { printf 'Probe policy error: %s browser adapter requires date-pattern and wait-seconds\n' "$dataset_id" >&2; return 1; }
      ;;
    *)
      printf 'Probe policy error: %s has unsupported adapter %s\n' "$dataset_id" "$adapter" >&2
      return 1
      ;;
  esac
}

render_dynamic_url() {
  local dataset_id="$1"
  local injected_date="$2"
  local template normalized_date year year_month rendered

  template="$(probe_policy_value "$dataset_id" '.["dynamic-url"].template')" || {
    printf 'Probe policy error: %s requires a dynamic URL template\n' "$dataset_id" >&2
    return 1
  }
  case "$template" in
    "https://storage.data.gov.my/pricecatcher/pricecatcher_{YYYY-MM}.parquet"|\
    "https://storage.data.gov.my/transportation/ktmb/komuter_{YYYY}.csv"|\
    "https://storage.data.gov.my/transportation/ktmb/ets_{YYYY}.csv"|\
    "https://storage.data.gov.my/transportation/ktmb/intercity_{YYYY}.csv"|\
    "https://storage.data.gov.my/transportation/ktmb/komuter_utara_{YYYY}.csv"|\
    "https://storage.data.gov.my/transportation/ktmb/shuttle_tebrau_{YYYY}.csv"|\
    "https://storage.data.gov.my/transportation/vehicles_{YYYY}.csv"|\
    "https://storage.data.gov.my/transportation/cars_{YYYY}.csv"|\
    "https://storage.data.gov.my/transportation/motorcycles_{YYYY}.csv"|\
    "https://storage.data.gov.my/transportation/bus/brt_{YYYY}_daily.csv"|\
    "https://storage.data.gov.my/transportation/rail/rapidrail_{YYYY}_daily.csv")
      ;;
    *)
      printf 'Probe policy error: %s has unsafe dynamic URL template\n' "$dataset_id" >&2
      return 1
      ;;
  esac
  if [[ ! "$injected_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    printf 'Invalid injected probe date: %s\n' "$injected_date" >&2
    return 1
  fi
  normalized_date="$(date -u -d "$injected_date" +'%Y-%m-%d' 2>/dev/null)" || return 1
  if [[ "$normalized_date" != "$injected_date" ]]; then
    printf 'Invalid injected probe date: %s\n' "$injected_date" >&2
    return 1
  fi
  year="${injected_date:0:4}"
  year_month="${injected_date:0:7}"
  rendered="${template//\{YYYY-MM\}/$year_month}"
  printf '%s\n' "${rendered//\{YYYY\}/$year}"
}

extract_max_date() {
  local body_path="$1"
  local date_field="$2"
  local today

  today="$(date -u +'%Y-%m-%d')"

  jq -r --arg f "$date_field" --arg today "$today" '
    ($f | split(".")) as $path
    |
    if type == "array" then
      [.[] | getpath($path)]
    elif type == "object" then
      [getpath($path)]
    else []
    end
    | map(select(. != null) | if type == "string" then .[0:10] else . end)
    | map(select((type != "string") or . <= $today))
    | max
  ' "$body_path"
}

extract_min_date() {
  local body_path="$1"
  local date_field="$2"

  jq -r --arg f "$date_field" '
    ($f | split(".")) as $path
    |
    if type == "array" then
      [.[] | getpath($path)]
    elif type == "object" then
      [getpath($path)]
    else []
    end
    | map(select(. != null) | if type == "string" then .[0:10] else . end)
    | min
  ' "$body_path"
}

data_gov_catalogue_page_url() {
  local dataset_id="$1"
  local source_url="$2"
  local canonical_id

  canonical_id="$(jq -er --arg id "$dataset_id" \
    'first(.datasets[] | select(.id == $id) | .canonical_id) // empty' \
    "$selected_manifest_file" 2>/dev/null || true)"
  if [[ -z "$canonical_id" ]]; then
    canonical_id="$(python3 - "$source_url" <<'PY'
import sys
from urllib.parse import parse_qs, urlparse

values = parse_qs(urlparse(sys.argv[1]).query).get("id", [])
if values:
    print(values[0])
PY
)"
  fi
  if [[ ! "$canonical_id" =~ ^[A-Za-z0-9_-]+$ ]]; then
    return 1
  fi
  printf 'https://data.gov.my/data-catalogue/%s\n' "$canonical_id"
}

extract_data_gov_page_date() {
  local page_path="$1"

  python3 - "$page_path" <<'PY'
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    page = Path(sys.argv[1]).read_text(encoding="utf-8")
    match = re.search(
        r"<script\b[^>]*\bid=(?:\"__NEXT_DATA__\"|'__NEXT_DATA__')[^>]*>(.*?)</script\s*>",
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise ValueError("missing __NEXT_DATA__")
    value = json.loads(match.group(1))["props"]["pageProps"]["data_as_of"]
    if not isinstance(value, str) or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", value
    ) is None:
        raise ValueError("invalid data_as_of")
    datetime.strptime(value, "%Y-%m-%d %H:%M")
except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
    pass
else:
    print(value[:10])
PY
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
    # Parquet magic-byte guard: parquet files start with "PAR1" (and end
    # with "PAR1"). They are binary — the CSV fallback below would
    # misinterpret random \n and comma bytes inside the compressed data
    # as row/column counts (pricecatcher reported garbage 2491 rows /
    # 4 cols from a binary file). Return null metrics so the caller's
    # estimate_parquet_rows path handles it instead.
    if head -c 4 "$body_path" 2>/dev/null | grep -q '^PAR1'; then
      jq -c -n \
        '{
          record_count: null,
          column_count: null,
          first_row: null,
          first_record_timestamp: null,
          body_format: "parquet"
        }'
      return 0
    fi
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

extract_npra_registration_format_metrics() {
  local body_path="$1"
  local counts legacy_count transition_count invalid_count total_count compatible

  counts="$(awk -F, '
    NR == 1 {
      header = $1
      gsub(/^"|"$/, "", header)
      gsub(/\r$/, "", header)
      if (header != "reg_no") exit 2
      next
    }
    {
      value = $1
      gsub(/^"|"$/, "", value)
      gsub(/\r$/, "", value)
      if (value == "") next
      total++
      upper = toupper(value)
      if (upper ~ /^MAL[0-9]{8}[A-Z]+$/) {
        legacy++
      } else if (upper ~ /^MAL[[:space:]]*(\+[[:space:]]*)?[0-9]{8}[[:space:]]*(\+[[:space:]]*)?[A-Z]+$/) {
        transition++
      } else {
        invalid++
      }
    }
    END { printf "%d\t%d\t%d\t%d\n", legacy, transition, invalid, total }
  ' "$body_path" 2>/dev/null)" || counts=$'0\t0\t1\t0'

  IFS=$'\t' read -r legacy_count transition_count invalid_count total_count <<< "$counts"
  compatible=false
  if (( total_count > 0 && invalid_count == 0 )); then
    compatible=true
  fi

  jq -cn \
    --argjson compatible "$compatible" \
    --argjson legacy "$legacy_count" \
    --argjson transition "$transition_count" \
    --argjson invalid "$invalid_count" \
    '{
      registration_format_compatible: $compatible,
      legacy_registration_count: $legacy,
      transition_registration_count: $transition,
      invalid_registration_count: $invalid
    }'
}

extract_npra_guidance_metrics() {
  local body_path="$1"
  local appendix_resource_count compatible

  appendix_resource_count="$(
    grep -oE '>Appendix[[:space:]]+[0-9]+[A-Z]?<' "$body_path" 2>/dev/null \
      | sed -E 's/^>Appendix[[:space:]]+//; s/<$//' \
      | sort -u \
      | wc -l \
      | tr -d '[:space:]'
  )"
  [[ "$appendix_resource_count" =~ ^[0-9]+$ ]] || appendix_resource_count=0
  compatible=false
  if (( appendix_resource_count >= 12 )); then
    compatible=true
  fi

  jq -cn \
    --argjson compatible "$compatible" \
    --argjson appendix_resource_count "$appendix_resource_count" \
    '{
      guidance_structure_compatible: $compatible,
      appendix_resource_count: $appendix_resource_count
    }'
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

emit_robots_blocked() {
  local dataset_id="$1"
  local source_url="$2"
  local origin details

  origin="$(printf '%s' "$source_url" | awk -F/ '{print $1"//"$3}')"
  printf 'Probe skipped: %s blocked by robots.txt at %s\n' \
    "$dataset_id" "$origin" >&2
  details="$(jq -cn --arg request_url "$source_url" \
    '{request_url: $request_url, access_method: "robots.txt compliance check"}')"
  emit "$dataset_id" "$source_url" "unreachable" \
    "Probe skipped: blocked by robots.txt" "$details"
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

  sleep 5

  # Poll for a non-empty snapshot until wait_seconds elapses, then have
  # camofox_timeout more seconds to land on a real snapshot. This is more
  # reliable than a single-shot wait-then-fetch for slow JSF sites where
  # the snapshot endpoint timing is jittery.
  local hard_deadline elapsed requested_snapshot snapshot_response current_at
  local attempt_at curl_timeout
  hard_deadline=$(( $(date +%s) + wait_seconds + camofox_timeout ))
  snapshot_response=""
  while (( $(date +%s) < hard_deadline )); do
    current_at=$(date +%s)
    elapsed=$((hard_deadline - current_at))
    if (( elapsed < 8 )); then
      curl_timeout=$elapsed
    else
      curl_timeout=$camofox_timeout
    fi
    if snapshot_response="$(curl --location --silent --show-error --fail \
      --max-time "$curl_timeout" \
      "${camofox_base_url}/tabs/${tab_id}/snapshot?userId=${user_id}" 2>/dev/null)"; then
      if jq -e 'has("snapshot") and (.snapshot | type == "string") and (.snapshot | length) > 100' <<< "$snapshot_response" >/dev/null 2>&1; then
        break
      fi
    fi
    sleep 2
  done
  if [[ -z "$snapshot_response" ]] || ! jq -e 'has("snapshot") and (.snapshot | type == "string") and (.snapshot | length) > 100' <<< "$snapshot_response" >/dev/null 2>&1; then
    close_camofox_tab "$tab_id" "$user_id" || true
    details="$(jq -cn --arg access_method 'Camofox' '{access_method: $access_method}')"
    emit "$dataset_id" "$source_url" "browser-dependent" "Camofox snapshot failed" "$details"
    return 0
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
  date_regex="$(probe_policy_value "$dataset_id" '.browser["date-pattern"]')" || return 1
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
  first_row_hash="$(jq -cS '.[0] // null' "$body_file" | python3 "$script_dir/shape_fingerprint.py" --json)"
  locations="$(jq '[.[].location.location_id] | unique | length' "$body_file")"
  date_start="$(jq -r '[.[].date] | min // empty' "$body_file")"
  date_end="$(jq -r '[.[].date] | max // empty' "$body_file")"
  content_freshness_date="$(DATAPULSE_CONTENT_FILE="$body_file" \
    DATAPULSE_PROBE_POLICY="$probe_policy" \
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
  local content_freshness_date content_request_url date_field extraction_mode
  local date_source metadata_page_url
  local metrics record_count column_count first_row_hash first_row body_format
  local estimated_record_count record_count_estimated incomplete
  local probe_status probe_message registration_metrics
  local registration_format_compatible legacy_registration_count
  local transition_registration_count invalid_registration_count special_validator
  local header_name header_value
  local -a request_header_args=()

  while IFS=$'\t' read -r header_name header_value; do
    request_header_args+=(--header "$header_name: $header_value")
  done < <(probe_policy_headers "$dataset_id")

  date_field="$(probe_policy_value "$dataset_id" '.freshness["content-date-field"]' 2>/dev/null || true)"
  extraction_mode="$(probe_policy_value "$dataset_id" '.freshness["extraction-mode"]' 2>/dev/null || true)"
  date_source="$(probe_policy_value "$dataset_id" '.freshness["date-source"]' 2>/dev/null || true)"
  if [[ -n "$date_field" && -z "$extraction_mode" ]]; then
    printf 'Probe policy error: %s content date field requires extraction-mode\n' "$dataset_id" >&2
    return 1
  fi
  # date_field is used later to parse the body's freshness date column.
  # We do NOT override the manifest URL here — direct-storage URLs in
  # the manifest are now the canonical source (the legacy data-catalogue
  # API was decommissioned).

  if ! respect_robots_txt "$dataset_id" "$request_url"; then
    emit_robots_blocked "$dataset_id" "$source_url"
    return 0
  fi

  : > "$headers_file"
  if ! http_status="$(curl --location --silent --show-error \
    --max-time "$curl_timeout" \
    "${request_header_args[@]}" \
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
      "${request_header_args[@]}" \
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
  body_format="$(jq -r '.body_format' <<< "$metrics")"
  estimated_record_count="null"
  record_count_estimated="false"
  incomplete="false"
  probe_status="fresh"
  probe_message="HTTP ${http_status}"
  registration_format_compatible="null"
  legacy_registration_count="null"
  transition_registration_count="null"
  invalid_registration_count="null"
  if [[ "$record_count" == "null" && "${request_url%%\?*}" == *.parquet ]]; then
    estimated_record_count="$(estimate_parquet_rows "$content_length")"
    if [[ "$estimated_record_count" != "null" ]]; then
      record_count="$estimated_record_count"
      record_count_estimated="true"
      incomplete="true"
    fi
  fi
  if [[ "$first_row" != "null" ]]; then
    first_row_hash="$(printf '%s' "$first_row" | python3 "$script_dir/shape_fingerprint.py" --json)"
  elif [[ "$body_format" == "csv" ]]; then
    first_row_hash="$(python3 "$script_dir/shape_fingerprint.py" --csv-headers < "$body_file")"
  else
    first_row_hash=""
  fi
  first_record_timestamp="$(jq -r '.first_record_timestamp // empty' <<< "$metrics")"
  content_freshness_date=""
  if [[ -n "$content_request_url" ]] && curl --location --silent --show-error --fail \
    --max-time "$curl_timeout" "${request_header_args[@]}" \
    --output "$content_body_file" "$content_request_url" 2>/dev/null; then
    if [[ "$extraction_mode" == "min" ]]; then
      content_freshness_date="$(extract_min_date "$content_body_file" "$date_field")"
    else
      content_freshness_date="$(extract_max_date "$content_body_file" "$date_field")"
    fi
  elif [[ -n "$date_field" ]] && jq -e . "$body_file" >/dev/null 2>&1; then
    if [[ "$extraction_mode" == "min" ]]; then
      content_freshness_date="$(extract_min_date "$body_file" "$date_field")"
    else
      content_freshness_date="$(extract_max_date "$body_file" "$date_field")"
    fi
  elif [[ -n "$date_field" ]]; then
    # CSV body: jq can't parse it, so extract the date column via awk.
    # Find the header row, locate the date column, then take max/min of the
    # ISO dates in that column. Only YYYY-MM-DD values are considered.
    if [[ "$extraction_mode" == "min" ]]; then
      content_freshness_date="$(awk -F, -v f="$date_field" '
        NR == 1 { for (i = 1; i <= NF; i++) if ($i == f) col = i; next }
        col && $col ~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}/ {
          if (min == "" || $col < min) min = $col
        }
        END { print min }
      ' "$body_file" 2>/dev/null)"
    else
      content_freshness_date="$(awk -F, -v f="$date_field" '
        NR == 1 { for (i = 1; i <= NF; i++) if ($i == f) col = i; next }
        col && $col ~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}/ {
          if (max == "" || $col > max) max = $col
        }
        END { print max }
      ' "$body_file" 2>/dev/null)"
    fi
  fi
  if [[ -n "$content_freshness_date" ]]; then
    [[ "$content_freshness_date" != "null" ]] || content_freshness_date=""
  fi
  if [[ -z "$content_freshness_date" && "$date_source" == "data.gov.my-page" ]]; then
    metadata_page_url="$(data_gov_catalogue_page_url "$dataset_id" "$source_url" || true)"
    if [[ -n "$metadata_page_url" ]] \
      && respect_robots_txt "$dataset_id" "$metadata_page_url" \
      && curl --location --silent --show-error --fail \
        --max-time "$curl_timeout" --output "$content_body_file" \
        "$metadata_page_url" 2>/dev/null; then
      content_freshness_date="$(extract_data_gov_page_date "$content_body_file")"
    fi
  fi
  special_validator="$(probe_policy_value "$dataset_id" '.["special-validator"]' 2>/dev/null || true)"
  case "$special_validator" in
    "")
      ;;
    npra-registration-format)
      registration_metrics="$(extract_npra_registration_format_metrics "$body_file")"
      registration_format_compatible="$(jq '.registration_format_compatible' <<< "$registration_metrics")"
      legacy_registration_count="$(jq '.legacy_registration_count' <<< "$registration_metrics")"
      transition_registration_count="$(jq '.transition_registration_count' <<< "$registration_metrics")"
      invalid_registration_count="$(jq '.invalid_registration_count' <<< "$registration_metrics")"
      if [[ "$registration_format_compatible" != "true" ]]; then
        probe_status="degraded"
        probe_message="HTTP ${http_status}; incompatible NPRA registration number format"
      fi
      ;;
    *)
      printf 'Probe policy error: %s validator %s is not valid for the direct adapter\n' \
        "$dataset_id" "$special_validator" >&2
      return 1
      ;;
  esac
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
    --argjson registration_format_compatible "$registration_format_compatible" \
    --argjson legacy_registration_count "$legacy_registration_count" \
    --argjson transition_registration_count "$transition_registration_count" \
    --argjson invalid_registration_count "$invalid_registration_count" \
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
      registration_format_compatible: $registration_format_compatible,
      legacy_registration_count: $legacy_registration_count,
      transition_registration_count: $transition_registration_count,
      invalid_registration_count: $invalid_registration_count,
      first_row_hash: (if $first_row_hash == "" then null else $first_row_hash end),
      first_record_timestamp: (
        if $first_record_timestamp == "" then null else $first_record_timestamp end
      )
    }')"
  emit "$dataset_id" "$source_url" "$probe_status" "$probe_message" "$details"
}

extract_hansard_probe_metrics() {
  local dataset_id="$1"
  local probe_output_file="$2"

  jq -ce --arg id "$dataset_id" '
    if .status != "ok" then error(.error // "Hansard probe did not return ok")
    elif $id == "hansard_sittings" then
      (.katalog | to_entries) as $chambers
      | if ($chambers | length) != 3
          or any($chambers[]; (.value.http_status // 0) != 200)
        then error("Hansard katalog endpoints were incomplete or unreachable")
        else {
          http_status: 200,
          record_count: ([$chambers[].value.sittings_total] | add),
          content_freshness_date: ([$chambers[].value.latest] | max)
        }
        end
    elif $id == "hansard_parliamentary_terms" then
      {
        http_status: 200,
        record_count: .takwim.total_terms,
        content_freshness_date: .takwim.current_term_end
      }
    elif $id == "hansard_mps" then
      if (.mps.http_status // 0) != 200
        then error("Hansard MP endpoint was unreachable")
        else {
          http_status: 200,
          record_count: .mps.total_mps,
          content_freshness_date: (
            .mps.last_modified // .freshness.content_freshness_date
            | if type == "string" then .[0:10] else . end
          )
        }
        end
    else error("Unsupported Hansard dataset id")
    end
    | if (.record_count | type) != "number"
        or .record_count < 0
        or (.content_freshness_date | type) != "string"
        or (.content_freshness_date | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$") | not)
      then error("Hansard probe returned invalid metrics")
      else .
      end
  ' "$probe_output_file"
}

check_hansard_script_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local hansard_probe_script="/home/redza/hansard-probe/probe_hansard.sh"
  local probe_output_file metrics details http_status record_count
  local content_freshness_date

  if ! respect_robots_txt "$dataset_id" "$source_url"; then
    emit_robots_blocked "$dataset_id" "$source_url"
    return 0
  fi

  probe_output_file="$(mktemp)"
  if [[ ! -r "$hansard_probe_script" ]] \
    || ! bash "$hansard_probe_script" > "$probe_output_file" 2>/dev/null \
    || ! metrics="$(extract_hansard_probe_metrics "$dataset_id" "$probe_output_file" 2>/dev/null)"; then
    rm -f "$probe_output_file"
    details="$(jq -cn --arg request_url "$source_url" \
      '{request_url: $request_url, access_method: "Hansard probe script"}')"
    emit "$dataset_id" "$source_url" "unreachable" \
      "Hansard probe script failed" "$details"
    return 0
  fi
  rm -f "$probe_output_file"

  http_status="$(jq '.http_status' <<< "$metrics")"
  record_count="$(jq '.record_count' <<< "$metrics")"
  content_freshness_date="$(jq -r '.content_freshness_date' <<< "$metrics")"
  details="$(jq -cn \
    --arg request_url "$source_url" \
    --argjson http_status "$http_status" \
    --argjson record_count "$record_count" \
    --arg content_freshness_date "$content_freshness_date" \
    '{
      request_url: $request_url,
      access_method: "Hansard probe script",
      http_status: $http_status,
      record_count: $record_count,
      content_freshness_date: $content_freshness_date
    }')"
  emit "$dataset_id" "$source_url" "fresh" "HTTP ${http_status}" "$details"
}

check_npra_guidance_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local http_status content_length last_modified guidance_metrics
  local guidance_structure_compatible appendix_resource_count status message details

  : > "$headers_file"
  if ! http_status="$(curl --location --silent --show-error \
    --max-time "$curl_timeout" \
    --dump-header "$headers_file" \
    --output "$body_file" --write-out '%{http_code}' "$source_url" 2>/dev/null)"; then
    details="$(jq -cn --arg request_url "$source_url" \
      '{request_url: $request_url, access_method: "direct curl GET"}')"
    emit "$dataset_id" "$source_url" "unreachable" "curl request failed" "$details"
    return 0
  fi
  if [[ ! "$http_status" =~ ^2[0-9][0-9]$ ]]; then
    emit_http_failure "$dataset_id" "$source_url" "$source_url" "$http_status"
    return 0
  fi

  content_length="$(wc -c < "$body_file" | tr -d '[:space:]')"
  last_modified="$(awk 'BEGIN { IGNORECASE=1 } /^last-modified:/ { sub(/^[^:]+:[[:space:]]*/, ""); value=$0 } END { gsub("\\r", "", value); print value }' "$headers_file")"
  if [[ -n "$last_modified" ]]; then
    last_modified="$(date -u -d "$last_modified" +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || true)"
  fi

  guidance_metrics="$(extract_npra_guidance_metrics "$body_file")"
  guidance_structure_compatible="$(jq '.guidance_structure_compatible' <<< "$guidance_metrics")"
  appendix_resource_count="$(jq '.appendix_resource_count' <<< "$guidance_metrics")"
  status="fresh"
  message="HTTP ${http_status}"
  if [[ "$guidance_structure_compatible" != "true" ]]; then
    status="degraded"
    message="HTTP ${http_status}; fewer than 12 NPRA DRGD appendix resources"
  fi

  details="$(jq -cn \
    --arg request_url "$source_url" \
    --argjson http_status "$http_status" \
    --argjson content_length "$content_length" \
    --arg last_modified "$last_modified" \
    --argjson guidance_structure_compatible "$guidance_structure_compatible" \
    --argjson appendix_resource_count "$appendix_resource_count" \
    '{
      request_url: $request_url,
      access_method: "direct curl GET",
      http_status: $http_status,
      content_length: $content_length,
      last_modified: (if $last_modified == "" then null else $last_modified end),
      record_count: $appendix_resource_count,
      column_count: null,
      guidance_structure_compatible: $guidance_structure_compatible,
      appendix_resource_count: $appendix_resource_count
    }')"
  emit "$dataset_id" "$source_url" "$status" "$message" "$details"
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

dispatch_policy_adapter() {
  local dataset_id="$1"
  local source_url="$2"
  local adapter wait_seconds

  adapter="$(probe_adapter "$dataset_id")" || return 1
  validate_adapter_config "$dataset_id" "$adapter" || return 1
  case "$adapter" in
    direct)
      check_direct_dataset "$dataset_id" "$source_url"
      ;;
    weather)
      check_weather_dataset "$dataset_id" "$source_url"
      ;;
    browser)
      wait_seconds="$(probe_policy_value "$dataset_id" '.browser["wait-seconds"]')" || return 1
      check_browser_dataset "$dataset_id" "$source_url" "$wait_seconds"
      ;;
    gtfs-static|gtfs-realtime)
      check_gtfs_dataset "$dataset_id" "$source_url"
      ;;
    hansard-script)
      check_hansard_script_dataset "$dataset_id" "$source_url"
      ;;
  esac
}

dispatch_dataset() {
  local dataset_id="$1"
  local source_url="$2"
  local dataset_result_file="$3"
  local dynamic_template special_validator injected_date

  results_file="$dataset_result_file"
  body_file="${dataset_result_file}.body"
  content_body_file="${dataset_result_file}.content"
  headers_file="${dataset_result_file}.headers"
  : > "$results_file"

  dynamic_template="$(probe_policy_value "$dataset_id" '.["dynamic-url"].template' 2>/dev/null || true)"
  if [[ -n "$dynamic_template" ]]; then
    injected_date="${DATAPULSE_PROBE_DATE:-$(date -u +'%Y-%m-%d')}"
    source_url="$(render_dynamic_url "$dataset_id" "$injected_date")" || return 1
  fi

  special_validator="$(probe_policy_value "$dataset_id" '.["special-validator"]' 2>/dev/null || true)"
  case "$special_validator" in
    npra-guidance-appendices)
      check_npra_guidance_dataset "$dataset_id" "$source_url"
      ;;
    ""|npra-registration-format)
      dispatch_policy_adapter "$dataset_id" "$source_url"
      ;;
    *)
      printf 'Probe policy error: %s has unsupported special validator %s\n' \
        "$dataset_id" "$special_validator" >&2
      return 1
      ;;
  esac
}

if [[ "${DATAPULSE_CHECK_SOURCE_ONLY:-false}" == true ]]; then
  return 0
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
done < <(jq -r --slurpfile policy "$probe_policy" '
  .datasets[]
  | select(($policy[0].datasets[.id].adapter // $policy[0].defaults.adapter) != "browser")
  | [.id, .url]
  | @tsv
' "$selected_manifest_file")
wait

: > "$results_file"
if (( dataset_index > 0 )); then
  for result_path in "$probe_results_dir"/*.json; do
    cat "$result_path" >> "$results_file"
  done
fi

# Serial browser probe pass: Camofox serializes tab opens, and parallel opens
# can exhaust the curl time budget on slow JSF sites such as ePerolehan.
if jq -e --slurpfile policy "$probe_policy" \
  'any(.datasets[]; (($policy[0].datasets[.id].adapter // $policy[0].defaults.adapter) == "browser"))' \
  "$selected_manifest_file" >/dev/null; then
  camofox_warmed=false
  while IFS= read -r browser_id; do
    if ! jq -e --arg id "$browser_id" \
      '.datasets[] | select(.id == $id)' "$selected_manifest_file" >/dev/null; then
      continue
    fi
    source_url="$(jq -r --arg id "$browser_id" \
      '.datasets[] | select(.id == $id) | .url' "$selected_manifest_file")"
    [[ -n "$source_url" ]] || continue
    printf -v browser_result '%s/browser-%s.json' "$probe_results_dir" "$browser_id"
    if ! respect_robots_txt "$browser_id" "$source_url"; then
      (
        results_file="$browser_result"
        : > "$results_file"
        emit_robots_blocked "$browser_id" "$source_url"
      )
    else
      if ! $camofox_warmed; then
        warm_camofox_browser
        camofox_warmed=true
      fi
      (dispatch_dataset "$browser_id" "$source_url" "$browser_result")
    fi
    cat "$browser_result" >> "$results_file"
  done < <(jq -r '.datasets | to_entries[] | select(.value.adapter == "browser") | .key' "$probe_policy")
fi

expected_count="$(jq '.datasets | length' "$selected_manifest_file")"
actual_count="$(wc -l < "$results_file" | tr -d '[:space:]')"
if [[ "$actual_count" != "$expected_count" ]]; then
  printf 'Internal error: expected %s results, wrote %s\n' "$expected_count" "$actual_count" >&2
  exit 1
fi

if $due_mode && (( expected_count == 0 )) && [[ -s "$previous_file" ]]; then
  cat "$previous_file"
  if $compare_health; then
    python3 "$script_dir/compare_health.py" "$previous_file" "$manifest" >&2
  fi
  exit 0
fi

checked_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
checked_epoch="$(date -u -d "$checked_at" +%s)"
build_health_snapshot() {
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
      elif $frequency == "hourly" then 0.04
      elif $frequency == "30 seconds" then 0.0003
      elif $frequency | startswith("biennial") then 730
      elif $frequency | startswith("as-required") then null
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
      | ([$last_modified_age, $content_freshness_age] | map(select(. != null)) | max // null) as $staleness_days
      | ((($old.column_count | type) == "number"
            and ($probe.column_count | type) == "number"
            and $old.column_count != $probe.column_count)
          or (($old.first_row_hash | type) == "string"
            and ($probe.first_row_hash | type) == "string"
            and ($old.first_row_hash | startswith("shape-v1:"))
            and ($probe.first_row_hash | startswith("shape-v1:"))
            and $old.first_row_hash != $probe.first_row_hash)) as $shape_changed
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
         elif $staleness_days != null then
           # Null cadence (as-required or unmapped): use a conservative 90-day default.
           if $staleness_days <= 135 then "fresh"
           elif $staleness_days <= 270 then "aging"
           else "stale"
           end
         else "unknown-freshness"
         end) as $staleness_status
      | (if ($entry.data_type // "") == "reference" then
           null
         elif ($entry.discontinued // false) then
           "discontinued"
         elif ($staleness_days != null and $staleness_days > 730) then
           "discontinued"
         else null
         end) as $discontinued_status
      | (if $discontinued_status != null then
           $discontinued_status
         elif ($probe.access_method // "" | ascii_downcase) == "camofox" then
           "browser-dependent"
         elif (($probe.http_status | type) != "number" or $probe.http_status < 200 or $probe.http_status >= 300) then
           "unreachable"
         # Reference data is versioned rather than time-series, so no freshness clock applies.
         elif ($entry.data_type // "") == "reference" then
           "reference"
         elif $probe.status == "degraded" then
           "degraded"
         elif $staleness_status == "unknown-freshness" then "unknown-freshness"
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
          registration_format_compatible: ($probe.registration_format_compatible // null),
          legacy_registration_count: ($probe.legacy_registration_count // null),
          transition_registration_count: ($probe.transition_registration_count // null),
          invalid_registration_count: ($probe.invalid_registration_count // null),
          guidance_structure_compatible: ($probe.guidance_structure_compatible // null),
          appendix_resource_count: ($probe.appendix_resource_count // null),
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
  | (reduce ["fresh", "aging", "stale", "discontinued", "degraded", "browser-dependent", "unreachable", "unknown", "unknown-freshness", "reference"][] as $status
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
}

if $compare_health; then
  build_health_snapshot > "$comparison_output_file"
  cat "$comparison_output_file"
  python3 "$script_dir/compare_health.py" "$comparison_output_file" "$manifest" >&2
else
  build_health_snapshot
fi
