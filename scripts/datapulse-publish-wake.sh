#!/usr/bin/env bash
set -Eeuo pipefail

# Installed copies need no arguments or working-directory configuration.
# Path overrides should be absolute; defaults share the pipeline's runtime tree.
readonly REPO="${DATAPULSE_REPO:-/srv/datapulse-my}"
readonly PUBLISH_UNIT="${DATAPULSE_PUBLISH_UNIT:-datapulse-health-publish.service}"
readonly PUBLICATION_STATE="${DATAPULSE_PUBLICATION_STATE:-$REPO/var/log/publication-in-flight.sha}"
readonly PUBLISH_WAKE_STATE="${DATAPULSE_PUBLISH_WAKE_STATE:-$REPO/var/log/publish-wake-main.sha}"
# 120s bounds requests to 3 per five minutes (ceil(300/120)), or 8 per
# 15-minute cycle (ceil(900/120)), while a one-minute tick avoids a 300s retry.
readonly PUBLISH_WAKE_REARM="${DATAPULSE_PUBLISH_WAKE_REARM_SECONDS:-120}"

log() {
  printf 'PUBLISH_WAKE: %s\n' "$*" >&2
}

PUBLISH_WAKE() {
  # Admission belongs exclusively to the pipeline; only observe marker presence.
  [[ -f "$PUBLICATION_STATE" ]] || return 0

  local remote head previous="" state last_start=0 now status temporary_state
  if [[ ! "$PUBLISH_WAKE_REARM" =~ ^[1-9][0-9]{0,8}$ ]]; then
    log 'invalid wake re-arm interval; five-minute timer remains fallback'
    return 0
  fi
  # One bounded remote read, without fetching or modifying repository refs.
  # Capture diagnostics too: remote URLs may contain credentials, so log status only.
  if remote=$(GIT_TERMINAL_PROMPT=0 timeout --kill-after=5s 20s \
    git -C "$REPO" ls-remote --exit-code --refs origin refs/heads/main 2>&1); then
    :
  else
    status=$?
    log "remote main read failed (exit $status); five-minute timer remains fallback"
    return 0
  fi
  if [[ "$remote" =~ ^([[:xdigit:]]{40}|[[:xdigit:]]{64})$'\t'refs/heads/main$ ]]; then
    head="${BASH_REMATCH[1]}"
  else
    log 'invalid remote main response; five-minute timer remains fallback'
    return 0
  fi

  if [[ -f "$PUBLISH_WAKE_STATE" ]]; then
    if ! state=$(cat -- "$PUBLISH_WAKE_STATE"); then
      log 'wake state could not be read; five-minute timer remains fallback'
      return 0
    fi
    previous="${state%%$'\n'*}"
    # A legacy head-only state has no request time: allow one start to seed it.
    if [[ "$state" == *$'\n'* ]]; then
      last_start="${state#*$'\n'}"
    fi
  fi
  if [[ ! "$last_start" =~ ^[0-9]{1,12}$ ]]; then
    log 'invalid wake request time; five-minute timer remains fallback'
    return 0
  fi
  if ! now=$(date +%s) || [[ ! "$now" =~ ^[0-9]{1,12}$ ]]; then
    log 'wake time could not be read; five-minute timer remains fallback'
    return 0
  fi
  # A new head may start immediately once without a recorded request. After
  # that, both triggers share a cooldown, even if main changes on every tick.
  if [[ "$head" == "$previous" ]] || (( 10#$last_start != 0 )); then
    (( 10#$now - 10#$last_start >= PUBLISH_WAKE_REARM )) || return 0
  fi

  # Record both values atomically before requesting a start, including failures.
  if ! mkdir -p -- "$(dirname -- "$PUBLISH_WAKE_STATE")"; then
    log 'wake state directory could not be created; five-minute timer remains fallback'
    return 0
  fi
  temporary_state="${PUBLISH_WAKE_STATE}.tmp.$$"
  if ! { printf '%s\n%s\n' "$head" "$now" > "$temporary_state" &&
    mv -f -- "$temporary_state" "$PUBLISH_WAKE_STATE"; }; then
    rm -f -- "$temporary_state"
    log 'wake state could not be recorded; five-minute timer remains fallback'
    return 0
  fi
  if ! systemctl --no-block start "$PUBLISH_UNIT"; then
    log 'publish start request failed; five-minute timer remains fallback'
  fi
}

PUBLISH_WAKE
