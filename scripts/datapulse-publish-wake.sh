#!/usr/bin/env bash
set -Eeuo pipefail

# Installed copies need no arguments or working-directory configuration.
# Path overrides should be absolute; defaults share the pipeline's runtime tree.
readonly REPO="${DATAPULSE_REPO:-/srv/datapulse-my}"
readonly PUBLISH_UNIT="${DATAPULSE_PUBLISH_UNIT:-datapulse-publish.service}"
readonly PUBLICATION_STATE="${DATAPULSE_PUBLICATION_STATE:-$REPO/var/log/publication-in-flight.sha}"
readonly PUBLISH_WAKE_STATE="${DATAPULSE_PUBLISH_WAKE_STATE:-$REPO/var/log/publish-wake-main.sha}"

log() {
  printf 'PUBLISH_WAKE: %s\n' "$*" >&2
}

PUBLISH_WAKE() {
  # Admission belongs exclusively to the pipeline; only observe marker presence.
  [[ -f "$PUBLICATION_STATE" ]] || return 0

  local remote head previous="" status temporary_state
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
    if ! previous=$(cat -- "$PUBLISH_WAKE_STATE"); then
      log 'wake state could not be read; five-minute timer remains fallback'
      return 0
    fi
  fi
  [[ "$head" != "$previous" ]] || return 0

  # Remember before requesting a start: unchanged main must not cause repeat starts.
  if ! mkdir -p -- "$(dirname -- "$PUBLISH_WAKE_STATE")"; then
    log 'wake state directory could not be created; five-minute timer remains fallback'
    return 0
  fi
  temporary_state="${PUBLISH_WAKE_STATE}.tmp.$$"
  if ! { printf '%s\n' "$head" > "$temporary_state" &&
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
