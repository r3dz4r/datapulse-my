#!/usr/bin/env bash

smoke_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$smoke_script_dir/.." && pwd)"
cd "$repo_root" || exit 1

DATAPULSE_CHECK_SOURCE_ONLY=true
# shellcheck source=scripts/check.sh
source "$smoke_script_dir/check.sh"
unset DATAPULSE_CHECK_SOURCE_ONLY

set -uo pipefail

browser_datasets=(
  doe_apims
  doe_rqims
  doe_mqims
  kkm_idengue
  eperolehan-diklankan
)

declare -A smoke_status=()
declare -A smoke_snapshot_chars=()
declare -A smoke_duration=()

now_ms() {
  date +%s%3N
}

format_duration() {
  local duration_ms="$1"
  local duration_seconds

  duration_seconds="$(jq -nr --argjson ms "$duration_ms" '$ms / 1000')"
  printf '%.1f' "$duration_seconds"
}

run_browser_smoke() {
  local dataset_id="$1"
  local source_url="$2"
  local wait_seconds="$3"
  local user_id="datapulse-check-${dataset_id}"
  local started_ms poll_started_ms poll_deadline_ms hard_deadline_ms current_ms
  local remaining_ms request_timeout open_response tab_id snapshot_response snapshot=""
  local finished_ms

  started_ms="$(now_ms)"
  if ! open_response="$(curl --location --silent --show-error --fail \
    --max-time "$camofox_timeout" \
    --request POST "${camofox_base_url}/tabs/open" \
    --header 'Content-Type: application/json' \
    --data "$(jq -cn --arg userId "$user_id" --arg url "$source_url" \
      '{userId: $userId, url: $url}')" 2>/dev/null)"; then
    printf 'ERROR: %s /tabs/open request failed\n' "$dataset_id" >&2
    smoke_status["$dataset_id"]="FAIL"
    smoke_snapshot_chars["$dataset_id"]="-"
    finished_ms="$(now_ms)"
    smoke_duration["$dataset_id"]="$(format_duration "$((finished_ms - started_ms))")"
    return
  fi

  tab_id="$(jq -r '.tabId // empty' <<< "$open_response" 2>/dev/null)"
  if [[ -z "$tab_id" ]]; then
    printf 'ERROR: %s /tabs/open returned no tabId\n' "$dataset_id" >&2
    smoke_status["$dataset_id"]="FAIL"
    smoke_snapshot_chars["$dataset_id"]="-"
    finished_ms="$(now_ms)"
    smoke_duration["$dataset_id"]="$(format_duration "$((finished_ms - started_ms))")"
    return
  fi

  poll_started_ms="$(now_ms)"
  poll_deadline_ms=$((poll_started_ms + wait_seconds * 1000))
  hard_deadline_ms=$((poll_deadline_ms + 5000))

  # Let initial navigation start before snapshot requests compete for the tab.
  sleep 5

  while (( $(now_ms) < poll_deadline_ms )); do
    current_ms="$(now_ms)"
    remaining_ms=$((hard_deadline_ms - current_ms))
    request_timeout=$(((remaining_ms + 999) / 1000))
    (( request_timeout > camofox_timeout )) && request_timeout="$camofox_timeout"
    (( request_timeout < 1 )) && request_timeout=1

    snapshot_response=""
    if snapshot_response="$(curl --location --silent --show-error --fail \
      --max-time "$request_timeout" \
      "${camofox_base_url}/tabs/${tab_id}/snapshot?userId=${user_id}" 2>/dev/null)"; then
      snapshot="$(jq -r '.snapshot // empty' <<< "$snapshot_response" 2>/dev/null)"
      if [[ -n "$snapshot" ]]; then
        break
      fi
    fi

    (( $(now_ms) < poll_deadline_ms )) && sleep 1
  done

  finished_ms="$(now_ms)"
  if [[ -n "$snapshot" ]]; then
    smoke_status["$dataset_id"]="OK"
    smoke_snapshot_chars["$dataset_id"]="${#snapshot}"
  else
    printf 'ERROR: %s /tabs/%s/snapshot timed out after %ss + 5s slack\n' \
      "$dataset_id" "$tab_id" "$wait_seconds" >&2
    smoke_status["$dataset_id"]="FAIL"
    smoke_snapshot_chars["$dataset_id"]="-"
  fi
  smoke_duration["$dataset_id"]="$(format_duration "$((finished_ms - started_ms))")"

  if ! close_camofox_tab "$tab_id" "$user_id"; then
    printf 'ERROR: %s could not close Camofox tab %s\n' "$dataset_id" "$tab_id" >&2
  fi
}

health_response=""
health_ok=true
if ! health_response="$(curl --silent --show-error --fail \
  --max-time "$camofox_timeout" "${camofox_base_url}/health" 2>/dev/null)" \
  || ! jq -e '.ok == true' <<< "$health_response" >/dev/null 2>&1; then
  printf 'ERROR: Camofox /health failed at %s/health\n' "$camofox_base_url" >&2
  health_ok=false
fi

failures=0
for dataset_id in "${browser_datasets[@]}"; do
  wait_seconds="${BROWSER_DATASET_WAIT[$dataset_id]:-15}"
  if $health_ok; then
    source_url="$(jq -r --arg id "$dataset_id" \
      '.datasets[] | select(.id == $id) | .url' datapulse.json | head -n 1)"
    if [[ -z "$source_url" ]]; then
      printf 'ERROR: %s has no URL in datapulse.json\n' "$dataset_id" >&2
      smoke_status["$dataset_id"]="FAIL"
      smoke_snapshot_chars["$dataset_id"]="-"
      smoke_duration["$dataset_id"]="0.0"
    else
      run_browser_smoke "$dataset_id" "$source_url" "$wait_seconds"
    fi
  else
    smoke_status["$dataset_id"]="FAIL"
    smoke_snapshot_chars["$dataset_id"]="-"
    smoke_duration["$dataset_id"]="0.0"
  fi
  [[ "${smoke_status[$dataset_id]}" == "FAIL" ]] && ((failures += 1))
done

printf '\n%-28s %-7s %-15s %-13s %s\n' \
  dataset_id status snapshot_chars wait_seconds duration
for dataset_id in "${browser_datasets[@]}"; do
  printf '%-28s %-7s %-15s %-13s %s\n' \
    "$dataset_id" \
    "${smoke_status[$dataset_id]}" \
    "${smoke_snapshot_chars[$dataset_id]}" \
    "${BROWSER_DATASET_WAIT[$dataset_id]:-15}" \
    "${smoke_duration[$dataset_id]}"
done

(( failures == 0 ))
