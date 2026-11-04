#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/.." && pwd)
readonly DEFAULT_REPO="${DATAPULSE_REPO:-${repo_root}}"
# The publish branch is parameterisable so the whole publish chain can be
# exercised against a sandbox clone without reaching the production channel.
# It defaults to the production branch, so behaviour is unchanged when
# DATAPULSE_PUBLISH_BRANCH is unset. This is a readonly constant on purpose: the
# sandbox interlock below compares against it, so that refusal cannot be lifted
# by an environment override.
readonly DEFAULT_PUBLISH_BRANCH=health-automation
readonly DEFAULT_MCP_SYNC_SCRIPT=/srv/datapulse-my/scripts/sync_mcp_deployment.sh
readonly DEFAULT_MCP_SYNC_STATE=/home/redza/.local/share/datapulse-mcp/.mcp-sync-state
readonly DEFAULT_MCP_SYNC_MAX_FAILURES=3
# Repeated publish deferrals must escalate instead of logging the same line at
# the same volume every cycle forever; this is the consecutive-deferral count at
# which one distinct escalation line is emitted.
readonly DEFAULT_PUBLISH_DEFERRAL_ALERT_THRESHOLD=3
# The five-minute timer gets 12 chances across three 1200-second publish windows.
readonly DEFAULT_PUBLICATION_HOLD_CEILING_SECONDS=3600
# Observation-time signing: the host that observes asks a separate identity to
# sign, over that signer's unix socket. The observing process no longer holds
# key material, so no private key path is configured here; the socket path is
# host state (never repository content), so it sits with the other DEFAULT_*
# constants and is overridable for tests.
readonly DEFAULT_OBSERVATION_SIGNER_SOCKET=/run/datapulse-signer/sign.sock
readonly DEFAULT_OBSERVATION_REGISTRY=/home/redza/.hermes/keys/datapulse-observation-registry.json
readonly DEFAULT_OBSERVATION_SIGN_TIMEOUT_SECONDS=60
# Allow a slow metadata walk without spending the producer's remaining window.
readonly SPOOL_HANDOFF_TIMEOUT_SECONDS=180
readonly COMMIT_MESSAGE='chore(health): update due dataset health'
readonly HEARTBEAT_COMMIT_PREFIX='chore(health): heartbeat'
# The receipts-only commit that binds a signed observation to the artifact
# commit that carries it. assert_managed_commits() must accept the subject so a
# receipt commit left local by a soft-failed push is publishable next cycle.
readonly OBSERVATION_COMMIT_PREFIX='chore(observation): sign observation'
readonly PENDING_BASE_REF=refs/datapulse/pending-base
# Frozen accepted projection: the attestation lane writes it; this runner only reads it.
readonly ATTESTATION_SCORE_PATH=attestations/latest/scores.json
# datapulse_summary.json is a served public surface (see config/public-surfaces.json in
# the product repo). It belongs in this list because it is regenerated every cycle from
# health/latest.json and must be committed in the SAME commit as the health snapshot it
# summarises -- otherwise the published summary drifts from the published health and the
# release gate (test_public_summary.py::test_committed_summary_matches_committed_health_snapshot)
# fails on the next push.
# The OKF bundle is a projection of the health snapshot (health/latest.json
# with datapulse.json and changelog.json), so it is listed as docs/okf and
# regenerated on the same schedule that moves the snapshot; before that stage
# existed nothing refreshed it and the committed projection drifted a fortnight
# behind the health data it described. Per-dataset pages are also regenerated
# from the snapshot each cycle and published through docs/datasets. docs as a
# whole stays absent: listing docs/ would let a stray file
# elsewhere under docs/ refuse publication while `git add -A` risked sweeping
# it into an artifact commit.
# observation-receipts/ holds the signed observation receipts and the chain head.
# The receipt is produced by run_observation_signing() AFTER the artifact commit,
# and names the newest ALREADY-PUBLISHED commit from refs/remotes/origin/main,
# materializing that commit's artifact bytes for the digest; the runner seeds
# run_dir/observation-receipts from the live checkout before staging so the swap
# preserves the accumulated chain, and the signed receipt is then committed in a
# second, receipts-only commit in the same cycle.
# The dynamic URL producer refreshes the manifest and its URL-bearing surfaces
# together. Publish them in that same transaction or a monthly roll leaves the
# required URL-drift check comparing the new observation with the old manifest.
readonly -a ARTIFACT_PATHS=(health badges feed.xml changelog.json catalog-snapshot.json catalog-graph.json datapulse_summary.json README.md record-evidence deltas docs/okf docs/datasets observation-receipts datapulse.json data/json data/jsonld docs/index.html)
readonly -a MANAGED_ARTIFACT_PATHS=("${ARTIFACT_PATHS[@]}")
# Four backoffs give a brief index refresh up to two seconds to finish.
readonly -a INDEX_LOCK_RETRY_DELAYS=(0.2 0.4 0.6 0.8)

# Python interpreter: prefer DATAPULSE_PYTHON_BIN (set by the systemd unit
# to the Hermes venv Python, which has httpx+pandas+jsonschema pre-installed),
# fall back to python3 from PATH. Without this override the pipeline uses
# /usr/bin/python3.12, which lacks the deps gen_record_evidence.py needs.
PYTHON_BIN="${DATAPULSE_PYTHON_BIN:-python3}"
MCP_SYNC_SCRIPT="${DATAPULSE_MCP_SYNC_SCRIPT:-$DEFAULT_MCP_SYNC_SCRIPT}"
DATAPULSE_MCP_SYNC_STATE="${DATAPULSE_MCP_SYNC_STATE:-$DEFAULT_MCP_SYNC_STATE}"
DATAPULSE_MCP_SYNC_MAX_FAILURES="${DATAPULSE_MCP_SYNC_MAX_FAILURES:-$DEFAULT_MCP_SYNC_MAX_FAILURES}"
DATAPULSE_PUBLISH_DEFERRAL_ALERT_THRESHOLD="${DATAPULSE_PUBLISH_DEFERRAL_ALERT_THRESHOLD:-$DEFAULT_PUBLISH_DEFERRAL_ALERT_THRESHOLD}"
OBSERVATION_SIGNER_SOCKET="${DATAPULSE_OBSERVATION_SIGNER_SOCKET:-$DEFAULT_OBSERVATION_SIGNER_SOCKET}"
OBSERVATION_REGISTRY="${DATAPULSE_OBSERVATION_REGISTRY:-$DEFAULT_OBSERVATION_REGISTRY}"
OBSERVATION_SIGN_TIMEOUT_SECONDS="${DATAPULSE_OBSERVATION_SIGN_TIMEOUT_SECONDS:-$DEFAULT_OBSERVATION_SIGN_TIMEOUT_SECONDS}"
# A transient name-resolution gap (resolver restarted by unattended-upgrades
# mid-cycle) fails `git fetch` with 128 and, unguarded under set -e, became the
# script's own exit status with no attributable log line. The fetch is retried
# with bounded linear backoff; a persistent outage dies attributed instead.
FETCH_ATTEMPTS="${DATAPULSE_FETCH_ATTEMPTS:-5}"
FETCH_RETRY_BASE_SECONDS="${DATAPULSE_FETCH_RETRY_BASE_SECONDS:-5}"


repo="${DATAPULSE_REPO:-$DEFAULT_REPO}"
PUBLISH_BRANCH="${DATAPULSE_PUBLISH_BRANCH:-$DEFAULT_PUBLISH_BRANCH}"
old_origin=""
fetched_origin=""
fetched_publish_head=""
run_dir=""
run_dir_owned=false
spool_root="${DATAPULSE_HEALTH_SPOOL:-/var/lib/datapulse-observer/runtime/health-spool}"
publish_root=""
publish_root_owned=false
recovering_publish=false
publish_swapped=false
pending_ref_created=false
declare -a swapped_paths=()
declare -A old_target_moved=()
declare -A new_target_moved=()
telemetry_file=""
cycle=""
publication_buffered=false
publication_waiting=false
publish_recovery_attempted=false

log() {
  printf 'datapulse-health: %s\n' "$*"
}

telemetry() {
  local stage="$1" duration_ms="$2" status="$3" extra="${4-}"
  [ -z "$extra" ] && extra='{}'
  if ! DATAPULSE_TELEMETRY_FILE="$telemetry_file" DATAPULSE_CYCLE="$cycle" \
    ${PYTHON_BIN} "$run_dir/scripts/check_heartbeat.py" append \
      --stage "$stage" --duration "$duration_ms" --status "$status" \
      --extra-json "$extra"; then
    log "telemetry write failed for stage $stage"
  fi
}

milliseconds() { date +%s%3N; }

die() {
  printf 'datapulse-health: %s\n' "$*" >&2
  exit 1
}

git_repo() {
  case "${1:-}" in
    fetch|push|ls-remote)
      GIT_TERMINAL_PROMPT=0 timeout --kill-after=5s 60s git -C "$repo" "$@"
      ;;
    *) git -C "$repo" "$@" ;;
  esac
}

git_repo_index_retry() {
  local attempt=1 rc output

  while :; do
    if output="$(git_repo "$@" 2>&1)"; then
      [[ -z "$output" ]] || printf '%s\n' "$output"
      return 0
    else
      rc=$?
    fi
    if [[ "$output" != *index.lock* \
        || ( "$output" != *"File exists"* \
          && "$output" != *"Another git process seems to be running"* ) ]] \
        || (( attempt > ${#INDEX_LOCK_RETRY_DELAYS[@]} )); then
      [[ -z "$output" ]] || printf '%s\n' "$output" >&2
      return "$rc"
    fi
    log "publish index lock collision; retrying git operation ($attempt/${#INDEX_LOCK_RETRY_DELAYS[@]})"
    sleep "${INDEX_LOCK_RETRY_DELAYS[attempt-1]}"
    attempt=$((attempt + 1))
  done
}

# 0 = artifacts computed from the snapshot may still be published.
# 1 = the snapshot is on neither origin/main nor the publish branch, so the
#     history it was computed from has moved out from under it.
# 2 = local HEAD moved during the probe (a writer other than this cycle).
publish_base_current() {
  local snapshot="$1" current_origin="$2" current_head="$3"
  local remote_publish_head=""

  [[ "$current_head" == "$snapshot" ]] || return 2
  [[ "$snapshot" == "$current_origin" ]] && return 0
  if git_repo merge-base --is-ancestor "$snapshot" "$current_origin"; then
    return 0
  fi

  # The artifacts do not travel through origin/main: they are pushed to the
  # automation branch and reach main through the automation pull request. A
  # snapshot already published on that branch is therefore publishable even
  # when main advanced into a sibling while the probe ran. This is the same
  # question reconcile_after_publish asks, so the gate and the reconcile agree
  # on what "published" means.
  remote_publish_head="$(git_repo rev-parse --verify --quiet "refs/remotes/origin/$PUBLISH_BRANCH" || :)"
  if [[ -n "$remote_publish_head" ]] \
      && git_repo merge-base --is-ancestor "$snapshot" "$remote_publish_head"; then
    return 0
  fi
  return 1
}

assert_repository() {
  [[ -d "$repo/.git" ]] || die "repository missing: $repo"
  git_repo rev-parse --verify HEAD >/dev/null 2>&1 || die "repository has no HEAD: $repo"
}

# Normalise a path for comparison without requiring it to exist, so a trailing
# slash or a symlinked spelling of the production checkout cannot slip past the
# sandbox interlock below.
canonical_path() {
  if command -v realpath >/dev/null 2>&1; then
    realpath -m -- "$1" 2>/dev/null || printf '%s\n' "$1"
    return 0
  fi
  printf '%s\n' "$1"
}

# Sandbox interlock: a publish branch other than the production value marks a
# sandbox exercise, so it must never run against the production checkout -- a
# stray artifact commit would otherwise reach the live branch. The comparison
# uses the readonly DEFAULT_REPO constant rather than an overridable variable,
# so the refusal cannot be lifted from the environment that chose the branch.
# This is a hard refusal, not a warning and not a silent skip.
assert_publish_target_safe() {
  [[ "$PUBLISH_BRANCH" == "$DEFAULT_PUBLISH_BRANCH" ]] && return 0
  if [[ "$(canonical_path "$repo")" == "$(canonical_path "$DEFAULT_REPO")" ]]; then
    die "refusing to run: publish branch '$PUBLISH_BRANCH' is not the production branch but the repository is the production checkout $DEFAULT_REPO; point DATAPULSE_REPO at a sandbox clone"
  fi
}

assert_no_git_operation() {
  local state

  for state in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
    if [[ -e "$(git_repo rev-parse --git-path "$state")" ]]; then
      die "control-plane degraded: unfinished Git operation ($state) in $repo"
    fi
  done
}

fetch_origin_with_retry() {
  local attempt=1 allow_failure=false
  local output=""

  [[ "${1-}" == --allow-failure ]] && allow_failure=true

  while (( attempt <= FETCH_ATTEMPTS )); do
    if output="$(git_repo fetch origin main 2>&1)"; then
      return 0
    fi
    log "control-plane fetch origin/main attempt $attempt/$FETCH_ATTEMPTS failed: ${output//$'\n'/; }"
    if (( attempt < FETCH_ATTEMPTS )); then
      sleep "$(( FETCH_RETRY_BASE_SECONDS * attempt ))"
    fi
    attempt=$(( attempt + 1 ))
  done
  if [[ "$allow_failure" == true ]]; then
    return 1
  fi
  die "control-plane degraded: cannot fetch origin/main after ${FETCH_ATTEMPTS} attempts: ${output//$'\n'/; }"
}

fetch_origin() {
  old_origin="$(git_repo rev-parse --verify --quiet refs/remotes/origin/main || :)"
  log "control-plane fetch origin/main"
  fetch_origin_with_retry
  fetched_origin="$(git_repo rev-parse --verify refs/remotes/origin/main)" \
    || die "control-plane degraded: refs/remotes/origin/main missing after fetch"

  if [[ -n "$old_origin" && "$old_origin" != "$fetched_origin" ]] \
    && ! git_repo merge-base --is-ancestor "$old_origin" "$fetched_origin"; then
    die "control-plane degraded: origin/main history was rewritten ($old_origin -> $fetched_origin)"
  fi
}

# A forced update of the bot branch can leave its local tracking ref behind.
# Read only that branch, with a time bound, before admitting or pushing a publish.
refresh_publish_branch() {
  local output rc

  fetched_publish_head=""
  if output="$(GIT_TERMINAL_PROMPT=0 timeout --kill-after=5s 60s git -C "$repo" fetch \
      --no-tags --no-recurse-submodules origin \
      "+refs/heads/$PUBLISH_BRANCH:refs/remotes/origin/$PUBLISH_BRANCH" 2>&1)"; then
    fetched_publish_head="$(git_repo rev-parse --verify "refs/remotes/origin/$PUBLISH_BRANCH")" \
      && return 0
  else
    # A missing branch is a normal first publish. Confirm absence separately:
    # a transport failure must never turn a stale ref into an unleased push.
    if GIT_TERMINAL_PROMPT=0 timeout --kill-after=5s 60s git -C "$repo" ls-remote \
        --exit-code --heads origin "refs/heads/$PUBLISH_BRANCH" >/dev/null 2>&1; then
      rc=0
    else
      rc=$?
    fi
    [[ "$rc" == 2 ]] && return 0
  fi
  log "publish deferred: cannot refresh origin/$PUBLISH_BRANCH: ${output//$'\n'/; }"
  telemetry publish.push 0 skipped '{"reason":"publish_branch_fetch_failed"}'
  return 1
}

# The paths this pipeline is allowed to write into its own commits. The commit
# validator and the recovery's discard decision both read this one predicate so
# the two cannot drift: a path the pipeline may commit is a path whose local
# regeneration may be discarded when it obstructs a recovery reset.
path_is_pipeline_managed() {
  case "$1" in
    health/*|badges/*|feed.xml|changelog.json|catalog-snapshot.json|catalog-graph.json|datapulse_summary.json|README.md|record-evidence/*|docs/*|deltas/*|observation-receipts/*|datapulse.json|data/json/*|data/jsonld/*) return 0 ;;
    *) return 1 ;;
  esac
}

# A commit on an origin tracking ref has remote provenance even when its subject
# is outside the pipeline vocabulary. Only commits absent from every such ref
# need the local subject and path checks below; subject alone cannot establish
# whether a commit is local-only.
commit_reachable_from_origin() {
  local commit="$1" ref

  while IFS= read -r ref; do
    if git_repo merge-base --is-ancestor "$commit" "$ref"; then
      return 0
    fi
  done < <(git_repo for-each-ref --format='%(refname)' refs/remotes/origin/)
  return 1
}

assert_managed_commits() {
  local base="$1"
  local commit subject path
  local count=0

  while IFS= read -r commit; do
    [[ -n "$commit" ]] || continue
    count=$((count + 1))
    if commit_reachable_from_origin "$commit"; then
      continue
    fi
    subject="$(git_repo show -s --format=%s "$commit")"
    [[ "$subject" == "$COMMIT_MESSAGE" \
      || "$subject" =~ ^chore\(health\):\ heartbeat\ [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ \
      || "$subject" =~ ^chore\(observation\):\ sign\ observation\ [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ \
      || "$subject" =~ ^chore\(attestations\):\ commit\ signed\ envelopes\ for\ [0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] \
      || die "control-plane degraded: local-only commit is not pipeline-managed: $commit ($subject)"

    while IFS= read -r path; do
      path_is_pipeline_managed "$path" \
        || die "control-plane degraded: pipeline commit $commit changed disallowed path: $path"
    done < <(git_repo diff-tree --no-commit-id --name-only -r "$commit")
  done < <(git_repo rev-list --reverse "$base..HEAD")

  (( count > 0 )) || die "control-plane degraded: expected a local pipeline commit above $base"
}

assert_artifacts_clean() {
  local status unpublished remote_publish_head count
  local -a tracked_paths=()

  status="$(git_repo status --porcelain -- "${MANAGED_ARTIFACT_PATHS[@]}")"
  [[ -z "$status" ]] && return 0
  unpublished="$(git_repo rev-list HEAD --not refs/remotes/origin/main)" \
    || die "control-plane degraded: cannot check unpublished commits before artifact restore"
  if [[ -n "$unpublished" ]]; then
    remote_publish_head="$(git_repo rev-parse --verify --quiet "refs/remotes/origin/$PUBLISH_BRANCH" || :)"
    [[ -n "$remote_publish_head" ]] \
      && git_repo merge-base --is-ancestor HEAD "$remote_publish_head" \
      || die "control-plane degraded: artifact paths have uncommitted changes; refusing to overwrite: ${status//$'\n'/; }"
  fi

  mapfile -d '' -t tracked_paths < <(git_repo diff --no-renames --name-only -z HEAD -- "${MANAGED_ARTIFACT_PATHS[@]}")
  if (( ${#tracked_paths[@]} > 0 )); then
    git_repo_index_retry restore --source=HEAD --staged --worktree -- "${tracked_paths[@]}" \
      || die "control-plane degraded: artifact paths restore failed"
  fi
  # restore does not remove untracked generator output, including staged additions
  # that become untracked when the index is restored.
  git_repo_index_retry clean -fd -- "${MANAGED_ARTIFACT_PATHS[@]}" \
    || die "control-plane degraded: artifact paths restore failed"
  [[ -z "$(git_repo status --porcelain -- "${MANAGED_ARTIFACT_PATHS[@]}")" ]] \
    || die "control-plane degraded: artifact paths restore failed"
  count="$(printf '%s\n' "$status" | wc -l)"
  log "artifact guard restored $count managed paths to HEAD"
}

# `reset --keep` refuses when a path that differs between HEAD and the target also
# has local changes. assert_artifacts_clean() only inspects MANAGED_ARTIFACT_PATHS,
# so a pipeline-managed path outside that list -- assert_managed_commits() accepts
# every commit under docs/*, which the guard deliberately leaves out -- passes the
# guard and still wedges the reset. That is the 2026-10-05 lock: the same
# divergence was re-derived and the same reset refused on 210 consecutive cycles
# across four hours. Clear local changes only to the paths that actually overlap
# the reset and that the pipeline owns (it regenerates them every cycle). Decide
# that in a first pass and touch nothing when any obstruction is unmanaged, so the
# caller's existing refusal still fires with the working tree exactly as it was.
# The probe must default to reporting untracked files: `reset --keep` refuses an
# untracked file at a target path just as it refuses a modified tracked one, and
# the old untracked-excluding probe skipped exactly that case -- neither
# classified as managed (so not cleared) nor as unmanaged (so no refusal) -- which
# reproduced the same permanent deadlock in a second shape. Only paths in the
# HEAD-to-target difference are ever probed, so an unrelated untracked file is
# never touched.
# Returns 0 when the reset can proceed, 1 when an unmanaged obstruction remains.
clear_managed_reset_obstructions() {
  local target="$1"
  local path status
  local -a managed=()
  local -a unmanaged=()

  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    status="$(git_repo status --porcelain -- "$path")"
    [[ -n "$status" ]] || continue
    if path_is_pipeline_managed "$path"; then
      managed+=("$path")
    else
      unmanaged+=("$path")
    fi
  done < <(git_repo diff --name-only --no-renames HEAD "$target")

  (( ${#unmanaged[@]} == 0 )) || return 1

  for path in "${managed[@]}"; do
    log "control-plane recovery discarding local changes to pipeline-managed $path"
    if git_repo cat-file -e "HEAD:$path" 2>/dev/null; then
      git_repo checkout -q HEAD -- "$path" || return 1
    else
      git_repo rm -f -q -- "$path" 2>/dev/null || rm -f -- "$repo/$path" || return 1
    fi
  done
  return 0
}

publish_min_interval_seconds() {
  local interval="${DATAPULSE_PUBLISH_MIN_INTERVAL_SECONDS:-1200}"

  [[ "$interval" =~ ^[1-9][0-9]*$ ]] \
    || die "DATAPULSE_PUBLISH_MIN_INTERVAL_SECONDS must be a positive integer"
  printf '%s\n' "$interval"
}

publish_state_path() {
  printf '%s\n' "${DATAPULSE_PUBLISH_STATE:-$repo/var/log/publish-coalesce-state}"
}

publish_state_mark() {
  local state now tmp

  # The admission record must be durable before recording the softer cadence
  # timestamp. A failed timestamp write may retry; a missing SHA may race CI.
  if [[ "${1:-}" =~ ^[0-9a-f]{40}$ ]]; then
    publication_state_mark "$1"
  fi
  state="$(publish_state_path)"
  now="$(date -u +%s)"
  if ! mkdir -p "$(dirname "$state")" 2>/dev/null; then
    log "warning: publish coalesce state directory could not be created; continuing health cycle"
    return 0
  fi
  tmp="${state}.tmp.$$"
  if printf '%s\n' "$now" > "$tmp" && mv -f -- "$tmp" "$state"; then
    return 0
  fi
  rm -f -- "$tmp" || :
  log "warning: publish coalesce state could not be written; continuing health cycle"
  return 0
}

publication_state_path() {
  printf '%s\n' "${DATAPULSE_PUBLICATION_STATE:-$repo/var/log/publication-in-flight.sha}"
}

publication_receipt_path() {
  printf '%s\n' "${DATAPULSE_PUBLICATION_RECEIPT:-$repo/var/log/publication-admission.log}"
}

# Machine-readable exceeded-hold verdict at var/log/publication-hold-exceeded.json.
# Fields: pending_sha, age_seconds, ceiling_seconds, observed_at (Unix epoch).
# A guard that took the expiry transition adds state (the state left) and
# successor (the state taken); the check-hold probe takes none and omits both.
publication_hold_state_path() {
  printf '%s\n' "$repo/var/log/publication-hold-exceeded.json"
}

publication_hold_measure() {
  local pending="$1" committed now

  hold_ceiling_seconds="${DATAPULSE_PUBLICATION_HOLD_CEILING_SECONDS:-$DEFAULT_PUBLICATION_HOLD_CEILING_SECONDS}"
  [[ "$hold_ceiling_seconds" =~ ^[1-9][0-9]*$ ]] \
    || die "DATAPULSE_PUBLICATION_HOLD_CEILING_SECONDS must be a positive integer"
  now="${DATAPULSE_NOW_EPOCH:-$(date +%s)}"
  [[ "$now" =~ ^[0-9]+$ ]] || die "DATAPULSE_NOW_EPOCH must be a non-negative integer"
  committed="$(git_repo log -1 --format=%ct "$pending")" \
    || die "publication commit timestamp could not be read: $pending"
  [[ "$committed" =~ ^[0-9]+$ ]] \
    || die "publication commit timestamp is invalid: $pending"
  hold_observed_at="$now"
  hold_age_seconds=$(( now - committed ))
  (( hold_age_seconds >= 0 )) || hold_age_seconds=0
  (( hold_age_seconds > hold_ceiling_seconds ))
}

publication_hold_state_write() {
  local pending="$1" left="${2:-}" successor="${3:-}" state tmp

  state="$(publication_hold_state_path)"
  tmp="${state}.tmp.$$"
  if ! mkdir -p -- "$(dirname -- "$state")" \
      || ! jq -n --arg pending "$pending" --argjson age "$hold_age_seconds" \
        --argjson ceiling "$hold_ceiling_seconds" --argjson observed "$hold_observed_at" \
        --arg left "$left" --arg successor "$successor" \
        '{pending_sha:$pending,age_seconds:$age,ceiling_seconds:$ceiling,observed_at:$observed}
         + (if $successor == "" then {} else {state:$left,successor:$successor} end)' > "$tmp" \
      || ! mv -f -- "$tmp" "$state"; then
    rm -f -- "$tmp"
    log "warning: publication hold state could not be written: $state"
  fi
  return 0
}

publication_hold_state_clear() {
  local pending="$1" reason="$2" quiet="${3:-false}" state

  state="$(publication_hold_state_path)"
  [[ -e "$state" || -L "$state" ]] || return 0
  if rm -f -- "$state"; then
    [[ "$quiet" == true ]] || log "publication hold cleared pending=$pending reason=$reason"
  else
    log "warning: publication hold state could not be removed: $state"
  fi
  return 0
}

check_publication_hold() {
  local pending

  assert_repository
  pending="$(publication_state_sha)" \
    || die "publication state validation failed"
  if [[ -n "$pending" ]] && publication_hold_measure "$pending"; then
    publication_hold_state_write "$pending"
    printf 'HELD pending=%s age=%s ceiling=%s\n' \
      "$pending" "$hold_age_seconds" "$hold_ceiling_seconds"
    return 1
  fi
  publication_hold_state_clear "${pending:-none}" below_ceiling true
  printf 'OK\n'
}

publication_state_mark() {
  local state tmp

  state="$(publication_state_path)"
  tmp="${state}.tmp.$$"
  mkdir -p -- "$(dirname -- "$state")" \
    || die "publication state directory could not be created: $state"
  if ! printf '%s\n' "$1" > "$tmp" || ! mv -f -- "$tmp" "$state"; then
    rm -f -- "$tmp"
    die "publication state could not be written after push: $state"
  fi
}

publication_state_sha() {
  local state pending
  local -a lines=()

  state="$(publication_state_path)"
  [[ -e "$state" || -L "$state" ]] || return 0
  [[ -f "$state" && -r "$state" ]] \
    || die "publication state is unreadable: $state"
  mapfile -t lines < "$state" \
    || die "publication state could not be read: $state"
  (( ${#lines[@]} <= 2 )) \
    || die "publication state has unexpected content: $state"
  [[ ${#lines[@]} -lt 2 || "${lines[1]}" == buffered=1 ]] \
    || die "publication state has unexpected content: $state"
  pending="${lines[0]:-}"
  [[ "$pending" =~ ^[0-9a-f]{40}$ ]] \
    || die "publication state has no valid SHA: $state"
  git_repo cat-file -e "${pending}^{commit}" \
    || die "publication commit is missing locally: $pending"
  printf '%s\n' "$pending"
}

publication_state_buffer() {
  local state pending tmp

  pending="$(publication_state_sha)" \
    || die "publication state validation failed"
  [[ -n "$pending" ]] || die "publication state missing while buffering artifacts"
  state="$(publication_state_path)"
  tmp="${state}.tmp.$$"
  if ! printf '%s\nbuffered=1\n' "$pending" > "$tmp" \
      || ! mv -f -- "$tmp" "$state"; then
    rm -f -- "$tmp"
    die "publication buffer state could not be written: $state"
  fi
}

publication_content_landed() {
  local pending="$1" base="$2" main="$3" candidate candidates rc path escaped
  local max_candidates=256 checked=0 shown=0
  local -a changed_paths=() missing_paths=()

  # Only the pending delta owns bytes that must land. Unchanged managed files
  # may advance independently. Disable rename detection so both halves of a
  # rename, deletions, additions and mode changes are checked exactly.
  mapfile -d '' -t changed_paths < <(git_repo --literal-pathspecs diff \
    --no-ext-diff --no-textconv --no-renames --name-only -z \
    "$base" "$pending" -- "${MANAGED_ARTIFACT_PATHS[@]}")
  wait "$!" || die "publication changed paths could not be read: $pending"
  publication_content_reason="publication content unproven pending=$pending paths=${#changed_paths[@]}"
  if (( ${#changed_paths[@]} == 0 )); then
    publication_content_reason+=" reason=no_managed_delta"
    return 1
  fi

  # At most 256 tree comparisons, each restricted to the P changed files:
  # O(min(C,256)*P) path comparisons for C commits since the merge-base. Prefer
  # recent evidence; evidence older than this window deliberately stays held.
  candidates="$(git_repo rev-list --max-count="$max_candidates" "$base..$main")" \
    || die "publication landing candidates could not be read: $pending"
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    checked=$((checked + 1))
    # Every changed path must match in ONE candidate, including mode and
    # absence. A patch-id ignores whitespace and cannot prove byte identity.
    if git_repo --literal-pathspecs diff --no-ext-diff --no-textconv --quiet \
        "$pending" "$candidate" -- "${changed_paths[@]}"; then
      return 0
    else
      rc=$?
      [[ "$rc" == 1 ]] || die "publication content comparison failed: $pending $candidate"
    fi
  done <<< "$candidates"

  mapfile -d '' -t missing_paths < <(git_repo --literal-pathspecs diff \
    --no-ext-diff --no-textconv --no-renames --name-only -z \
    "$pending" "$main" -- "${changed_paths[@]}")
  wait "$!" || die "publication unlanded paths could not be read: $pending"
  publication_content_reason+=" candidates=$checked limit=$max_candidates unlanded_at_main="
  # Bound the diagnostic independently of publication size; shell quoting
  # keeps unusual filenames on one line without making them pathspecs.
  for path in "${missing_paths[@]}"; do
    (( shown < 8 )) || break
    printf -v escaped '%q' "$path"
    publication_content_reason+=" ${escaped:0:160}"
    shown=$((shown + 1))
  done
  publication_content_reason+=" missing_count=${#missing_paths[@]}"
  return 1
}

# A pushed head owns the automation PR until it appears on main. The caller
# already fetched origin/main; a damaged journal cannot admit another publish.
publication_admission_guard() {
  local pending receipt base landed=false publication_content_reason=""

  publication_waiting=false
  pending="$(publication_state_sha)" \
    || die "publication state validation failed"
  [[ -n "$pending" ]] || return 0

  if git_repo merge-base --is-ancestor "$pending" "$fetched_origin"; then
    landed=true
  else
    # Squash merges replace commit identity. Check exact containment of the
    # pending delta without requiring unrelated managed paths to stand still.
    base="$(git_repo merge-base "$pending" "$fetched_origin")" \
      || die "publication commit and origin/main have no common base: $pending"
    if publication_content_landed "$pending" "$base" "$fetched_origin"; then
      landed=true
    fi
  fi
  if [[ "$landed" == true ]]; then
    # Before the first deferred cycle the checkout must still be clean. Once
    # we have buffered a cycle, its managed dirt is intentional and durable.
    if [[ "$(sed -n '2p' "$(publication_state_path)")" != buffered=1 ]]; then
      assert_artifacts_clean
    fi
    # Keep the old SHA until the next successful push replaces it. A gate or
    # commit failure later in this cycle must not strand buffered artifacts.
    publication_buffered=true
    publication_hold_state_clear "$pending" landed
    return 0
  fi

  refresh_publish_branch || return 1
  if [[ -z "$fetched_publish_head" ]] \
      || ! git_repo merge-base --is-ancestor "$pending" "$fetched_publish_head"; then
    # Clear only the journal; both commits and buffered working-tree bytes
    # survive. An empty journal would instead fail publication_state_sha.
    rm -f -- "$(publication_state_path)" \
      || die "superseded publication state could not be removed: $pending"
    publication_hold_state_clear "$pending" superseded
    log "publication superseded $pending by origin/$PUBLISH_BRANCH ${fetched_publish_head:-absent}; clearing pending marker"
    telemetry publish.gate 0 success \
      "{\"reason\":\"publication_superseded\",\"pending_sha\":\"$pending\",\"branch_head\":\"${fetched_publish_head:-absent}\"}"
    publication_buffered=true
    return 0
  fi

  if [[ "$(sed -n '2p' "$(publication_state_path)")" != buffered=1 ]]; then
    assert_artifacts_clean
  fi

  log "$publication_content_reason"
  receipt="$(publication_receipt_path)"
  mkdir -p -- "$(dirname -- "$receipt")" \
    || die "publication receipt directory could not be created: $receipt"
  printf 'publication_in_flight %s\n' "$pending" >> "$receipt" \
    || die "publication receipt could not be appended: $receipt"
  if publication_hold_measure "$pending"; then
    # Expiry is a transition, not another wait: spool_held -> candidate_rebuilt.
    # Clear only the journal, as the superseded path does; both commits and the
    # buffered bytes survive, and this cycle rebuilds from the newest buffered
    # artifacts. The push lease against the fetched publish head still refuses
    # a concurrent writer. The record stays until the next guard verdict.
    publication_hold_state_write "$pending" spool_held candidate_rebuilt
    log "publication hold exceeded pending=$pending age=$hold_age_seconds ceiling=$hold_ceiling_seconds"
    telemetry publish.hold_exceeded 0 fail \
      "{\"pending_sha\":\"$pending\",\"age_seconds\":$hold_age_seconds,\"ceiling_seconds\":$hold_ceiling_seconds,\"observed_at\":$hold_observed_at,\"state\":\"spool_held\",\"successor\":\"candidate_rebuilt\"}"
    rm -f -- "$(publication_state_path)" \
      || die "expired publication state could not be removed: $pending"
    log "publication hold expired pending=$pending state=spool_held successor=candidate_rebuilt; clearing pending marker"
    telemetry publish.gate 0 success \
      "{\"reason\":\"publication_hold_expired\",\"pending_sha\":\"$pending\",\"ceiling_seconds\":$hold_ceiling_seconds,\"state\":\"spool_held\",\"successor\":\"candidate_rebuilt\"}"
    publication_buffered=true
    return 0
  fi
  publication_hold_state_clear "$pending" below_ceiling
  publication_waiting=true
  log "publication in flight $pending; retaining regenerated artifacts for the next cycle"
  return 1
}

path_is_managed_artifact() {
  local owned
  for owned in "${MANAGED_ARTIFACT_PATHS[@]}"; do
    [[ "$1" == "$owned" || "$1" == "$owned/"* ]] && return 0
  done
  return 1
}

cycle_rebase_in_progress() {
  local git_dir
  git_dir="$(git_repo rev-parse --absolute-git-dir)" || return 1
  [[ -d "$git_dir/rebase-merge" || -d "$git_dir/rebase-apply" ]]
}

abort_cycle_rebase() {
  local original="$1"
  if cycle_rebase_in_progress; then
    timeout 60s git -C "$repo" rebase --abort \
      || die "publish reconcile rollback failed: rebase --abort refused"
  fi
  if [[ "$(git_repo rev-parse HEAD)" != "$original" ]]; then
    git_repo reset --hard "$original" >/dev/null \
      || die "publish reconcile rollback failed: reset to $original refused"
  fi
  [[ "$(git_repo rev-parse HEAD)" == "$original" ]] \
    || die "publish reconcile rollback failed: HEAD did not return to $original"
  [[ -z "$(git_repo status --porcelain --untracked-files=all)" ]] \
    || die "publish reconcile rollback failed: checkout is not clean"
}

# producer_takes_owned_version_on_conflict: replay only the cycle's commits on
# current main. A conflict on any path outside the declared managed set leaves
# the original branch and pending-base ref untouched.
reconcile_cycle_before_push() {
  local base="$1" original="$2" path changed joined pending_ref
  local -a conflicts=() outside=()

  git_repo merge-base --is-ancestor "$fetched_origin" "$original" && return 0
  [[ -n "$base" ]] || die "publish reconcile refused: missing cycle base"
  git_repo merge-base --is-ancestor "$base" "$original" \
    || die "publish reconcile refused: cycle base is not an ancestor of HEAD"
  [[ -z "$(git_repo status --porcelain --untracked-files=all)" ]] \
    || die "publish reconcile refused: checkout is not clean"
  pending_ref="$(git_repo rev-parse --verify --quiet "$PENDING_BASE_REF" || :)"

  log "publish reconcile cycle $original onto origin/main $fetched_origin"
  if ! GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true GIT_TERMINAL_PROMPT=0 \
      timeout 60s git -C "$repo" -c commit.gpgsign=false -c rerere.enabled=false \
        -c rebase.autostash=false -c rebase.updateRefs=false \
        rebase --merge --onto "$fetched_origin" "$base"; then
    if ! cycle_rebase_in_progress; then
      abort_cycle_rebase "$original"
      die "publish reconcile refused: rebase failed before it could be aborted"
    fi
    while cycle_rebase_in_progress; do
      conflicts=()
      outside=()
      mapfile -d '' -t conflicts < <(git_repo diff --name-only --diff-filter=U -z)
      if (( ${#conflicts[@]} == 0 )); then
        abort_cycle_rebase "$original"
        die "publish reconcile refused: rebase failed without resolvable conflicts"
      fi
      for path in "${conflicts[@]}"; do
        path_is_managed_artifact "$path" || outside+=("$path")
      done
      if (( ${#outside[@]} > 0 )); then
        joined=""
        for path in "${conflicts[@]}"; do
          printf -v changed '%q' "$path"
          joined+="${joined:+, }$changed"
        done
        log "publish reconcile refused: conflicts outside managed artifacts: $joined"
        abort_cycle_rebase "$original"
        die "publish failed: cycle reconciliation refused"
      fi
      for path in "${conflicts[@]}"; do
        if git_repo ls-files -u -- "$path" | grep -Eq '^[0-9]+ [0-9a-f]+ 3[[:space:]]'; then
          if ! git_repo checkout --theirs -- "$path" || ! git_repo add -- "$path"; then
            abort_cycle_rebase "$original"
            die "publish reconcile refused: could not take producer version of $path"
          fi
        elif ! git_repo rm -f -- "$path"; then
          abort_cycle_rebase "$original"
          die "publish reconcile refused: could not take producer deletion of $path"
        fi
      done
      if GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true GIT_TERMINAL_PROMPT=0 \
          timeout 60s git -C "$repo" -c commit.gpgsign=false -c rerere.enabled=false \
            -c rebase.autostash=false -c rebase.updateRefs=false rebase --continue; then
        break
      fi
    done
  fi
  if [[ "$(git_repo rev-parse HEAD)" == "$original" \
      || "$(git_repo rev-parse HEAD)" == "$fetched_origin" ]] \
      || ! git_repo merge-base --is-ancestor "$fetched_origin" HEAD; then
    abort_cycle_rebase "$original"
    die "publish reconcile refused: cycle commit was not replayed on origin/main"
  fi
  while IFS= read -r changed; do
    [[ -n "$changed" ]] || continue
    if ! path_is_managed_artifact "$changed"; then
      abort_cycle_rebase "$original"
      die "publish reconcile refused: replay changed disallowed path: $changed"
    fi
  done < <(git_repo diff --name-only "$fetched_origin" HEAD)
  if [[ -n "$pending_ref" ]]; then
    git_repo update-ref "$PENDING_BASE_REF" HEAD "$pending_ref" \
      || { abort_cycle_rebase "$original"; die "publish reconcile refused: pending base could not be updated"; }
  fi
  log "publish reconcile cycle ready at $(git_repo rev-parse HEAD)"
}

# Keep the leased transport shared with checkout recovery. Its caller supplies
# the fetched tip; refreshing it here would hide a concurrent publisher.
push_publish_head() {
  local expected="$1" source="${2:-HEAD}"
  local -a lease=()

  if [[ -n "$expected" ]]; then
    lease=("--force-with-lease=refs/heads/$PUBLISH_BRANCH:$expected")
  fi
  log "publish push $source:$PUBLISH_BRANCH (force-with-lease)"
  git_repo push "${lease[@]}" origin "$source:$PUBLISH_BRANCH"
}

push_head() {
  local head force=false interval state last now elapsed base remote_publish_head

  case "${1:-}" in
    '') ;;
    --force) force=true ;;
    *) die "publish failed: unknown push mode '$1'" ;;
  esac

  assert_repository
  assert_no_git_operation
  fetch_origin
  head="$(git_repo rev-parse HEAD)"
  # The push target is the automation branch, not main. Main can advance after
  # the probe snapshot, so the original commit may be its sibling. Ask first the
  # question publish_base_current asks of the probe base: the base is still
  # reachable from origin/main (main advanced past it), or it was published on
  # the automation branch (a squash merge replaced it). A base on neither branch
  # is a genuine rewrite and is still refused.
  base="$(git_repo rev-parse --verify --quiet "$PENDING_BASE_REF" || :)"
  remote_publish_head="$(git_repo rev-parse --verify --quiet "refs/remotes/origin/$PUBLISH_BRANCH" || :)"
  if ! git_repo merge-base --is-ancestor "$fetched_origin" "$head"; then
    if [[ -z "$base" ]]; then
      die "publish rejected: origin/main is not an ancestor of HEAD; refusing non-fast-forward push"
    fi
    if ! git_repo merge-base --is-ancestor "$base" "$fetched_origin" \
        && { [[ -z "$remote_publish_head" ]] \
             || ! git_repo merge-base --is-ancestor "$base" "$remote_publish_head"; }; then
      die "publish rejected: base $base is on neither origin/main nor origin/$PUBLISH_BRANCH; refusing non-fast-forward push"
    fi
  fi
  if [[ -n "${repo:-}" && "$head" == "$fetched_origin" ]]; then
    publication_admission_guard || {
      [[ "$publication_waiting" == true ]] && return 0
      return 1
    }
  fi
  # Validate only the commits this cycle adds, from the recorded base. The base
  # can be a main commit the squash merge has since replaced, so ranging from
  # fetched_origin would inspect unrelated main history and falsely refuse the
  # push; without a recorded base, fall back to origin/main as before.
  assert_managed_commits "${base:-$fetched_origin}"
  if [[ -n "${repo:-}" && "$head" != "$fetched_origin" ]]; then
    publication_admission_guard || {
      [[ "$publication_waiting" == true ]] && return 0
      return 1
    }
  fi

  # Publish to the long-lived automation branch, never to main: the datapulse-my
  # ruleset protecting main refuses any push whose required check has not run
  # (GH013), while the automation branch is unguarded. A companion workflow opens
  # a PR from this branch and auto-merges it through the check.
  #
  # The automation branch is a bot-owned publish channel, not a history: it is
  # overwritten with the current publish each cycle, so its branch point going
  # stale must not wedge the pipeline. The lease (rather than an unconditional
  # overwrite) refuses when the remote-tracking ref no longer matches the
  # remote, so a concurrent publisher is never clobbered by a stale local view.
  if ! interval="$(publish_min_interval_seconds)"; then
    return 1
  fi
  if ! "$force"; then
    state="$(publish_state_path)"
    if [[ -r "$state" ]] && last="$(<"$state")" \
        && [[ "$last" =~ ^[0-9]+$ ]]; then
      now="$(date -u +%s)"
      if (( last <= now )); then
        elapsed=$(( now - last ))
        if (( elapsed < interval )); then
          log "publish coalesced: elapsed ${elapsed}s, interval ${interval}s"
          telemetry publish.push 0 skipped \
            "{\"reason\":\"minimum_interval\",\"elapsed_seconds\":$elapsed,\"interval_seconds\":$interval}"
          return 0
        fi
      fi
    fi
  fi
  reconcile_cycle_before_push "$base" "$head"
  head="$(git_repo rev-parse HEAD)"
  refresh_publish_branch || return 1
  if ! push_publish_head "$fetched_publish_head"; then
    die "publish failed: origin moved during the transaction; local pipeline commit is pending"
  fi
  publish_state_mark "$head"
  git_repo update-ref -d "$PENDING_BASE_REF"
}

# After a successful publish the durable copy of the artifact commit lives on
# the remote automation branch, not on local main. Pushing HEAD to that branch
# (see push_head) no longer advances origin/main the way the old HEAD:main push
# did, so the checkout is left holding a pipeline commit origin/main does not
# contain. The companion workflow squash-merges the automation branch, which
# makes the published SHA unreachable from main by construction; once a later
# fetch had already moved refs/remotes/origin/main, preflight's recovery
# branches (which need either a pending-base ref or a moving origin/main) had
# no path back to agreement, and every five-minute tick died before the probe.
# Reconciling here returns the checkout to the state the next run expects.
#
# reset --keep discards origin/main..HEAD, so prove first that HEAD is an
# ancestor of the remote automation branch: every commit the reset drops is then
# already on the remote branch. A commit the remote branch does not carry -- a
# receipts-only commit created after the artifact push, which the next cycle
# publishes -- is never discarded. reset --keep (not --hard) also refuses to
# clobber unrelated uncommitted work instead of destroying it.
# Shared reconcile body. 0 = the checkout was reset onto origin/main; 1 = the
# local commit is not on the automation branch, so nothing changed (a hold);
# 2 = there is no fetched origin/main to reset to; 3 = the reset was refused
# because the working tree overlaps it. The caller decides whether a non-hold
# failure is fatal: the post-publish path dies, the in-cycle gate retry defers.
reconcile_publish_step() {
  local head remote_head

  [[ -n "$fetched_origin" ]] || return 2
  head="$(git_repo rev-parse HEAD)"
  remote_head="$(git_repo rev-parse --verify --quiet "refs/remotes/origin/$PUBLISH_BRANCH" || :)"
  if [[ -z "$remote_head" ]] || ! git_repo merge-base --is-ancestor "$head" "$remote_head"; then
    log "publish reconcile held: local HEAD $head is not on origin/$PUBLISH_BRANCH; leaving it for the next push"
    return 1
  fi
  log "publish reconcile local main $head -> origin/main $fetched_origin (published on origin/$PUBLISH_BRANCH $remote_head)"
  git_repo_index_retry reset --keep "$fetched_origin" || return 3
  return 0
}

# Keep generated commits off main. Retain the cycle branch after publication:
# squash promotion and a later force-publish need not retain the receipt SHA.
begin_publish_checkout() {
  local branch="datapulse-cycle-$(date -u +%Y%m%dT%H%M%S%N)-$$"

  git_repo checkout -q -b "$branch"
}

# A receipt committed after the artifact push has no future transport owner.
# Prove every intervening commit, rather than a net diff that can hide real
# work or a rename from outside the receipt tree. Merge parents are inspected
# too. Recovery only fast-forwards the fetched publish tip, preserving all
# remote history even though the shared transport also supports leased updates.
reattach_observation_commits() {
  local head="$1" published="$2" commits commit paths path quoted joined=""
  local actual_head actual_status
  local -a measured_paths=()

  commits="$(git_repo rev-list --reverse "$published..$head")" || return 1
  [[ -n "$commits" ]] || return 1
  while IFS= read -r commit; do
    # NUL delimiters preserve unusual filenames; quote only for the audit log.
    # pipefail keeps an unreadable commit from being accepted as an empty one.
    paths="$(git_repo diff-tree --root -m --no-commit-id --name-only \
        --no-renames -r -z "$commit" | while IFS= read -r -d '' path; do
          printf -v quoted '%q' "$path"
          if [[ "$path" != observation-receipts/* ]]; then
            log "publish reconcile refused: unaccounted commit $commit changed non-observation path $quoted" >&2
            exit 1
          fi
          printf '%s\n' "$quoted"
        done)" || return 1
    [[ -z "$paths" ]] || measured_paths+=("$paths")
  done <<< "$commits"
  if ! git_repo merge-base --is-ancestor "$published" "$head"; then
    log "publish reconcile refused: origin/$PUBLISH_BRANCH $published is not an ancestor of local HEAD $head; refusing non-fast-forward recovery"
    return 1
  fi
  if [[ "$publish_recovery_attempted" == true ]]; then
    log 'publish reconcile refused: observation recovery already attempted this cycle'
    return 1
  fi
  publish_recovery_attempted=true
  if ! push_publish_head "$published" "$head"; then
    log "publish reconcile refused: observation recovery push failed for $head; local commits retained"
    return 1
  fi
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    joined+="${joined:+, }$path"
  done < <(printf '%s\n' "${measured_paths[@]}" | LC_ALL=C sort -u)
  log "publish reconcile re-attached commits: ${commits//$'\n'/, }; paths: ${joined:-none}"
  if ! actual_head="$(git_repo rev-parse HEAD)" \
      || ! actual_status="$(git_repo --no-optional-locks status --porcelain --untracked-files=no)" \
      || [[ "$actual_head" != "$head" || -n "$actual_status" ]]; then
    log 'publish reconcile refused: checkout changed during observation recovery'
    return 1
  fi
}

# Fetch into private refs: a refusal must not advance origin/main, FETCH_HEAD,
# or the publish tracking ref. The old cached value is not proof of publication.
# Keep a durable local ref as well: the next force-publish and squash promotion
# can otherwise remove the last remote ref containing the original receipt SHA.
reconcile_checkout() {
  local head target published status dirty_diff="" old_main main rc=0 line count
  local probe="refs/datapulse/reconcile-$$" saved created=false

  assert_no_git_operation
  status="$(git_repo --no-optional-locks status --porcelain --untracked-files=no)" || return 1
  if [[ -n "$status" ]]; then
    dirty_diff="$(
      { git_repo --no-optional-locks diff --no-ext-diff --no-textconv --binary HEAD \
        && git_repo --no-optional-locks diff --cached --no-ext-diff --no-textconv --binary HEAD; } \
        | sha256sum
    )" || return 1
  fi
  head="$(git_repo rev-parse HEAD)" || return 1
  main="$(git_repo rev-parse --verify refs/heads/main)" || return 1
  old_main="$(git_repo rev-parse --verify refs/remotes/origin/main)" || return 1
  # Never overwrite a ref left by another operation, even with an unlikely PID
  # collision. Fetch is atomic so a missing branch cannot leave half the proof.
  if git_repo show-ref --verify --quiet "$probe/main" \
      || git_repo show-ref --verify --quiet "$probe/publish"; then
    log "publish reconcile refused: probe refs already exist"
    return 1
  fi
  if ! git_repo fetch --atomic --no-write-fetch-head --no-tags --no-recurse-submodules --refmap= origin \
      "refs/heads/main:$probe/main" "refs/heads/$PUBLISH_BRANCH:$probe/publish"; then
    log "publish reconcile refused: cannot fetch origin/main and origin/$PUBLISH_BRANCH"
    return 1
  fi
  target="$(git_repo rev-parse "$probe/main")"
  published="$(git_repo rev-parse "$probe/publish")"
  if ! git_repo merge-base --is-ancestor "$old_main" "$target"; then
    log "publish reconcile refused: origin/main history was rewritten"
    rc=1
  elif ! git_repo merge-base --is-ancestor "$main" "$target"; then
    log "publish reconcile refused: local main has commits absent from origin/main"
    rc=1
  elif [[ "$(git_repo rev-parse HEAD)" != "$head" ]] \
      || [[ "$(git_repo --no-optional-locks status --porcelain --untracked-files=no)" != "$status" ]] \
      || { [[ -n "$status" ]] \
        && [[ "$(
          { git_repo --no-optional-locks diff --no-ext-diff --no-textconv --binary HEAD \
            && git_repo --no-optional-locks diff --cached --no-ext-diff --no-textconv --binary HEAD; } \
            | sha256sum
        )" != "$dirty_diff" ]]; }; then
    log "publish reconcile refused: checkout changed during fetch"
    rc=1
  elif [[ -n "$status" ]] \
      && [[ -n "$(git_repo rev-list "$head" --not refs/remotes/origin/main)" ]] \
      && ! git_repo merge-base --is-ancestor "$head" "$published"; then
    log "publish reconcile refused: tracked modifications; leaving checkout unchanged"
    rc=1
  elif ! git_repo merge-base --is-ancestor "$head" "$target" \
      && ! git_repo merge-base --is-ancestor "$head" "$published"; then
    reattach_observation_commits "$head" "$published" || rc=1
  fi
  if (( rc == 0 )); then
    saved="refs/datapulse/published/$head"
    if [[ "$head" == "$target" ]]; then
      : # Already on main; no extra recovery ref is needed on a repeat run.
    elif ! git_repo show-ref --verify --quiet "$saved"; then
      git_repo update-ref "$saved" "$head" "" || rc=1
      [[ "$rc" != 0 ]] || created=true
    elif [[ "$(git_repo rev-parse "$saved")" != "$head" ]]; then
      rc=1
    fi
    if (( rc == 0 )) && [[ -n "$status" ]]; then
      if git_repo_index_retry restore --source="$head" --staged --worktree -- .; then
        count="$(printf '%s\n' "$status" | wc -l)"
        log "publish reconcile discarded $count tracked paths"
        while IFS= read -r line; do
          log "publish reconcile discarded tracked path: ${line:3}"
        done <<< "$status"
      else
        rc=1
      fi
    fi
    if (( rc == 0 )); then
      log "publish reconcile local HEAD $head -> origin/main $target"
      git_repo update-ref refs/remotes/origin/main "$target" "$old_main" || rc=1
    fi
    if (( rc == 0 )); then
      if git_repo_index_retry checkout --no-overwrite-ignore -q -B main "$target"; then
        fetched_origin="$target"
      else
        git_repo update-ref refs/remotes/origin/main "$old_main" "$target"
        rc=1
      fi
    fi
    if (( rc != 0 )) && [[ "$created" == true ]]; then
      git_repo update-ref -d "$saved" "$head"
    fi
  fi
  git_repo update-ref -d "$probe/main"
  git_repo update-ref -d "$probe/publish"
  return "$rc"
}

reconcile_after_publish() {
  reconcile_checkout \
    || die "control-plane degraded: publish checkout reconciliation refused"
}

# Answer the publish-base question, retrying once through the existing reconcile
# when the first answer refuses. Returns the codes of publish_base_current
# (0 publish, 1 base gone, 2 local HEAD moved). On a clean reconcile the
# checkout is reset onto the newest origin/main and the artifacts are re-based
# onto it, so the re-ask succeeds; on a hold the refusal stands and the caller
# defers. The retry never aborts the cycle itself.
publish_base_gate() {
  local snapshot="$1" rc=0 snapshot_rc=0 reconcile_rc=0 recheck=0

  publish_base_current "$snapshot" "$fetched_origin" "$(git_repo rev-parse HEAD)" || rc=$?
  if (( rc == 0 )); then
    return 0
  fi

  # Re-base only when the snapshot itself is acceptable. A snapshot that is on
  # neither origin/main nor the automation branch is a genuine rewrite, and a
  # reconcile that happened to reset local HEAD onto origin/main must not rescue
  # artifacts computed from it.
  publish_base_current "$snapshot" "$fetched_origin" "$snapshot" || snapshot_rc=$?
  (( snapshot_rc == 0 )) || return "$rc"

  reconcile_publish_step || reconcile_rc=$?
  (( reconcile_rc == 0 )) || return "$rc"

  recheck=0
  publish_base_current "$(git_repo rev-parse HEAD)" "$fetched_origin" "$(git_repo rev-parse HEAD)" || recheck=$?
  return "$recheck"
}

# The automation branch is a publish channel, not a history: each cycle it is
# overwritten with the current publish. That is only safe while the commit it
# is overwritten with is based on the newest origin/main -- otherwise the
# promotion pull request carries the same generated paths as main under a
# different lineage and conflicts on every regeneration (measured 2026-10-05:
# 707 changed files, mergeable=CONFLICTING, main stopped receiving health while
# the pipeline kept pushing). Establish that at the point of commit instead of
# relying on the post-push reconcile, so the push can only ever advance the
# branch from main.
#
# A local checkout parked on a previous publish is redundant once that publish
# is on origin/$PUBLISH_BRANCH (its content has been promoted, so local commits
# at or below it are), so re-base it onto fetched_origin. The safety proof is
# the one reconcile_publish_step makes: HEAD must be an ancestor of the remote
# publish branch, so a commit the branch does not carry -- a receipts-only
# commit created after the publish -- is never discarded. A genuine rewrite of
# the base still falls through to push_head's existing refuse-not-clobber guard.
# The reset is therefore not merely unlikely to lose an unpublished receipt; it
# proves it cannot. 0 = the checkout is forward of origin/main (or was moved
# there); 1 = a local commit is not on the publish branch and must be left for
# the next push; 2 = there is no fetched origin/main to align to; 3 = the reset
# was refused because the working tree overlaps it. The caller defers on 1/2/3.
align_publish_base() {
  local head remote_head

  [[ -n "$fetched_origin" ]] || return 2
  head="$(git_repo rev-parse HEAD)"
  # Already forward of the newest origin/main: the commit this cycle creates is
  # a descendant of it, so there is nothing to re-base.
  if git_repo merge-base --is-ancestor "$fetched_origin" "$head"; then
    return 0
  fi
  # A HEAD behind origin/main with no local commit above it is a pure
  # fast-forward; a reset drops nothing.
  if ! git_repo merge-base --is-ancestor "$head" "$fetched_origin"; then
    remote_head="$(git_repo rev-parse --verify --quiet "refs/remotes/origin/$PUBLISH_BRANCH" || :)"
    if [[ -z "$remote_head" ]] \
        || ! git_repo merge-base --is-ancestor "$head" "$remote_head"; then
      log "publish alignment held: local HEAD $head is not on origin/$PUBLISH_BRANCH; leaving it for the next push"
      return 1
    fi
  fi
  log "publish aligning local HEAD $head -> origin/main $fetched_origin"
  git_repo_index_retry reset --keep "$fetched_origin" || return 3
  return 0
}

preflight() {
  local head merge_base pending_base remote_publish_head publication_pending
  local -a lease=()

  assert_repository
  assert_no_git_operation
  fetch_origin
  head="$(git_repo rev-parse HEAD)"

  # The previous PR must finish before preflight retries a local receipt
  # commit. During the hold, managed artifacts in the checkout are intentional.
  publication_pending="$(publication_state_sha)"
  if [[ -n "$publication_pending" ]]; then
    if [[ "$head" == "$fetched_origin" ]] \
        || git_repo merge-base --is-ancestor "$head" "$fetched_origin"; then
      return 0
    fi
    if git_repo merge-base --is-ancestor "$fetched_origin" "$head"; then
      assert_managed_commits "$fetched_origin"
      return 0
    fi
    if git_repo merge-base --is-ancestor "$publication_pending" "$head"; then
      if [[ "$head" != "$publication_pending" ]]; then
        assert_managed_commits "$publication_pending"
      fi
      return 0
    fi
    merge_base="$(git_repo merge-base "$head" "$fetched_origin" || :)"
    die "control-plane degraded: HEAD and origin/main diverged at ${merge_base:-no-common-ancestor}"
  fi

  if [[ "$head" == "$fetched_origin" ]]; then
    git_repo update-ref -d "$PENDING_BASE_REF"
    assert_artifacts_clean
    log "control-plane ready at $head"
    return 0
  fi

  if git_repo merge-base --is-ancestor "$head" "$fetched_origin"; then
    log "control-plane fast-forward HEAD to origin/main"
    git_repo merge --ff-only "$fetched_origin"
    git_repo update-ref -d "$PENDING_BASE_REF"
    assert_artifacts_clean
    return 0
  fi

  if git_repo merge-base --is-ancestor "$fetched_origin" "$head"; then
    assert_managed_commits "$fetched_origin"
    assert_artifacts_clean
    if [[ "${1:-}" == --producer ]]; then
      log 'producer deferred: local pipeline commit needs publisher transport'
      exit 0
    fi
    log "control-plane found pending pipeline commit; retrying push before probe"
    refresh_publish_branch || return 1
    if [[ -n "$fetched_publish_head" ]]; then
      lease=("--force-with-lease=refs/heads/$PUBLISH_BRANCH:$fetched_publish_head")
    fi
    if git_repo push "${lease[@]}" origin "HEAD:$PUBLISH_BRANCH"; then
      log "control-plane push attempt 1 succeeded"
    else
      old_origin="$fetched_origin"
      log "control-plane push attempt 1 rejected; fetching origin/main before retry"
      if ! fetch_origin_with_retry --allow-failure; then
        die "control-plane degraded: pending pipeline commit could not be pushed"
      fi
      fetched_origin="$(git_repo rev-parse --verify refs/remotes/origin/main)" \
        || die "control-plane degraded: pending pipeline commit could not be pushed"
      [[ "$fetched_origin" != "$old_origin" ]] \
        || die "control-plane degraded: pending pipeline commit could not be pushed"
      git_repo merge-base --is-ancestor "$old_origin" "$fetched_origin" \
        || die "control-plane degraded: origin/main history was rewritten ($old_origin -> $fetched_origin)"
      reconcile_cycle_before_push "$old_origin" "$head"
      assert_managed_commits "$fetched_origin"
      refresh_publish_branch || return 1
      lease=()
      if [[ -n "$fetched_publish_head" ]]; then
        lease=("--force-with-lease=refs/heads/$PUBLISH_BRANCH:$fetched_publish_head")
      fi
      if git_repo push "${lease[@]}" origin "HEAD:$PUBLISH_BRANCH"; then
        log "control-plane push attempt 2 succeeded after origin/main advanced"
      else
        die "control-plane degraded: pending pipeline commit could not be pushed"
      fi
    fi
    publication_state_mark "$(git_repo rev-parse HEAD)"
    git_repo update-ref -d "$PENDING_BASE_REF"
    fetched_origin="$(git_repo rev-parse HEAD)"
    return 0
  fi

  merge_base="$(git_repo merge-base "$head" "$fetched_origin" || :)"
  pending_base="$(git_repo rev-parse --verify --quiet "$PENDING_BASE_REF" || :)"
  if [[ -n "$pending_base" ]]; then
    # The automation PR squash-merges, so the commit that travelled through it
    # is replaced, not carried forward: the recorded pending base can therefore
    # stop being reachable from origin/main even though origin/main only
    # advanced (fetch_origin has already refused a genuine rewrite). The base
    # and the artifacts built on it are superseded, so reset the checkout to
    # origin/main and clear the ref -- the recovery an operator performed by
    # hand -- instead of dying at this line on every subsequent cycle. A later
    # cycle regenerates the artifacts.
    if ! git_repo merge-base --is-ancestor "$pending_base" "$fetched_origin"; then
      log "control-plane recovering: pending base $pending_base was squashed away by origin/main $fetched_origin"
      assert_managed_commits "$pending_base"
      assert_artifacts_clean
      if ! clear_managed_reset_obstructions "$fetched_origin" \
          || ! git_repo reset --keep "$fetched_origin"; then
        die "control-plane degraded: superseded pending base recovery overlaps local working-tree changes"
      fi
      git_repo update-ref -d "$PENDING_BASE_REF"
      return 0
    fi
    [[ "$merge_base" == "$pending_base" ]] \
      || die "control-plane degraded: origin/main history was rewritten away from pending base $pending_base"
    assert_managed_commits "$pending_base"
    assert_artifacts_clean
    log "control-plane recovering orphaned pipeline commit after normal remote advance"
    if ! clear_managed_reset_obstructions "$fetched_origin" \
        || ! git_repo reset --keep "$fetched_origin"; then
      die "control-plane degraded: orphan recovery overlaps local working-tree changes"
    fi
    git_repo update-ref -d "$PENDING_BASE_REF"
    return 0
  fi

  if [[ -n "$old_origin" && "$old_origin" != "$fetched_origin" \
      && "$merge_base" == "$old_origin" ]] \
    && git_repo merge-base --is-ancestor "$old_origin" "$head" \
    && git_repo merge-base --is-ancestor "$old_origin" "$fetched_origin"; then
    assert_managed_commits "$old_origin"
    assert_artifacts_clean
    log "control-plane recovering orphaned pipeline commit after normal remote advance"
    if ! clear_managed_reset_obstructions "$fetched_origin" \
        || ! git_repo reset --keep "$fetched_origin"; then
      die "control-plane degraded: orphan recovery overlaps local working-tree changes"
    fi
    git_repo update-ref -d "$PENDING_BASE_REF"
    return 0
  fi

  remote_publish_head="$(git_repo rev-parse --verify --quiet "refs/remotes/origin/$PUBLISH_BRANCH" || :)"
  if [[ -n "$remote_publish_head" ]] \
    && git_repo merge-base --is-ancestor "$head" "$remote_publish_head"; then
    assert_managed_commits "$merge_base"
    assert_artifacts_clean
    log "control-plane recovering diverged pipeline commit already published on origin/$PUBLISH_BRANCH"
    if ! clear_managed_reset_obstructions "$fetched_origin" \
        || ! git_repo reset --keep "$fetched_origin"; then
      die "control-plane degraded: divergence recovery overlaps local working-tree changes"
    fi
    git_repo update-ref -d "$PENDING_BASE_REF"
    return 0
  fi

  die "control-plane degraded: HEAD and origin/main diverged at ${merge_base:-no-common-ancestor}"
}

validate_history_jsonl() {
  local history_file="$1"

  # `inputs` consumes one JSON value at a time; `first` stops the generator at
  # the first invalid row instead of constructing the whole history array.
  # Emit true when no invalid row exists so jq -e has a successful final value.
  jq -e -n '
    first(inputs | if (
      (.dataset_id | type == "string")
      and (.observed_at | type == "string")
      and (.cycle | type == "string")
      and (.status | type == "string")
      and (.probe_outcome == "success" or .probe_outcome == "error" or .probe_outcome == "timeout")
    ) then empty else 0 end) // true | . == true
  ' "$history_file" >/dev/null
}

validate_staged_output() {
  local expected_count actual_count

  expected_count="$(jq -er '.datasets | length' "$run_dir/datapulse.json")" \
    || die "probe validation failed: invalid dataset manifest"
  jq -e --argjson expected "$expected_count" '
    (.datasets | type == "array")
    and (.datasets | length == $expected)
    and (._trust_summary.datasets_total == $expected)
  ' "$run_dir/health/latest.json" >/dev/null \
    || die "probe validation failed: health/latest.json is invalid or has an unexpected dataset count"
  actual_count="$(jq -r '.datasets | length' "$run_dir/health/latest.json")"

  validate_history_jsonl "$run_dir/health/history.jsonl" \
    || die "probe validation failed: health/history.jsonl is invalid"
  jq -e '
    .schema == "datapulse/v1/health-history-daily"
    and (.retention_days | type == "number")
    and (.compacted_cycles | type == "array")
    and (.aggregates | type == "array")
  ' "$run_dir/health/history_daily.json" >/dev/null \
    || die "probe validation failed: health/history_daily.json is invalid"

  jq -e . "$run_dir/changelog.json" >/dev/null \
    || die "probe validation failed: changelog.json is invalid"
  jq -e --argjson expected "$expected_count" --slurpfile health "$run_dir/health/latest.json" '
    .generated_at == $health[0].checked_at
    and .health.checked_at == $health[0].checked_at
    and .manifest.datasets_total == $expected
    and .health.datasets_total == $expected
    and (.datasets | length == $expected)
  ' "$run_dir/catalog-snapshot.json" >/dev/null \
    || die "probe validation failed: catalog-snapshot.json is inconsistent with health/latest.json"
  jq -e '.node_count > 0 and .edge_count >= 0' "$run_dir/catalog-graph.json" >/dev/null \
    || die "probe validation failed: catalog-graph.json is invalid"
  (
    cd "$run_dir"
    ${PYTHON_BIN} - <<'PY'
import json
from pathlib import Path

from scripts.gen_record_evidence import validate_record_evidence

manifest = json.loads(Path("datapulse.json").read_text(encoding="utf-8"))
for dataset in manifest["datasets"]:
    if dataset.get("vertical") is not True:
        continue
    path = Path("record-evidence") / dataset["id"] / "latest.json"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_record_evidence(envelope, full=False)
    if errors:
        raise SystemExit(f"{path}: {'; '.join(errors)}")
PY
  ) || die "probe validation failed: record evidence is invalid"
  [[ -s "$run_dir/feed.xml" && -s "$run_dir/README.md" ]] \
    || die "probe validation failed: a generated artifact is empty"
  # Pages consumes generated dataset passports from the run directory.
  [[ -d "$run_dir/health" && -d "$run_dir/badges" && -d "$run_dir/docs" && -d "$run_dir/data/passports" ]] \
    || die "probe validation failed: an artifact directory is missing"
  jq -e '
    .schema == "datapulse/v1/trust-scores"
    and .methodology_version == 3
    and all(.datasets[];
      .methodology_version == 3
      and ((.component_availability | keys) == (.components | keys))
      and ((.component_availability | keys) ==
        ["cross_source_agreement","drift","freshness","reliability","trend"]))
  ' "$run_dir/$ATTESTATION_SCORE_PATH" >/dev/null \
    || die "probe validation failed: attestation score is not methodology v3"

  log "probe validated; $actual_count datasets present"
}

rollback_publish() {
  local target

  $publish_swapped || return 0
  git_repo restore --staged -- "${MANAGED_ARTIFACT_PATHS[@]}" >/dev/null 2>&1 || :
  for target in "${swapped_paths[@]}"; do
    # Only remove a live target that this transaction installed. In particular,
    # an old-to-backup failure leaves the original target in place.
    if [[ "${new_target_moved[$target]:-false}" == true ]]; then
      rm -rf "${repo:?}/${target:?}"
    fi
    if [[ "${old_target_moved[$target]:-false}" == true \
        && -e "$publish_root/backup/$target" ]]; then
      mkdir -p "$(dirname "$repo/$target")"
      mv "$publish_root/backup/$target" "$repo/$target"
    fi
  done
}

cleanup() {
  local rc=$?

  if [[ "$recovering_publish" == true ]]; then
    log "publish recovery failed (exit $rc); retaining rollback bytes and ready observation"
    return 0
  fi
  if (( rc != 0 )); then
    # TERM can arrive after commit returns but before publish_swapped is cleared.
    # A committed transaction is pending transport, never a rollback candidate.
    if [[ "$publish_swapped" == true && -n "$run_dir" \
        && ! -s "$run_dir/.handoff/artifact-commit" && -f "$run_dir/.handoff/transaction.json" ]] \
        && [[ "$(git_repo rev-parse HEAD)" != "$(jq -er .base "$run_dir/.handoff/transaction.json")" ]]; then
      publish_swapped=false
      record_spool_commit
    fi
    rollback_publish
    if $pending_ref_created && $publish_swapped; then
      git_repo update-ref -d "$PENDING_BASE_REF" >/dev/null 2>&1 || :
    fi
    printf 'datapulse-health: failed (exit %s)\n' "$rc" >&2
  fi
  if [[ "$publish_root_owned" == true && -n "$publish_root" ]]; then
    rm -rf -- "$publish_root"
    [[ -z "$run_dir" ]] || rm -f -- "$run_dir/.handoff/transaction.json"
  fi
  if [[ "$run_dir_owned" == true ]]; then
    spool_control abandon
  fi
}

# A run can be seeded before the checkout advances. Compare again at each
# receipt copy boundary against both the live tree and HEAD before moving bytes.
refuse_stale_receipt_copy() {
  local source="$1" source_head live_head tree_head committed_head committed_commit origin
  local replacement adopted_head path_count head_values

  source_head="$(jq -r '.sequence_number // empty' "$source/chain_head.json" 2>/dev/null || :)"
  live_head="$(jq -r '.sequence_number // empty' "$repo/observation-receipts/chain_head.json" 2>/dev/null || :)"
  committed_commit="$(git_repo rev-parse HEAD 2>/dev/null || :)"
  tree_head="$(git_repo show "$committed_commit:observation-receipts/chain_head.json" 2>/dev/null | jq -r '.sequence_number // empty' 2>/dev/null || :)"
  head_values="stale_receipt_head_values source=${source_head:-missing} live=${live_head:-missing} committed=${tree_head:-missing}"
  if [[ ! "$live_head" =~ ^[0-9]+$ || ! "$tree_head" =~ ^[0-9]+$ ]]; then
    log "stale receipt copy refused: missing or unparseable committed head ($head_values comparison=valid_heads)"
    return 1
  fi
  committed_head="$tree_head"
  origin=HEAD
  if (( 10#$live_head > 10#$tree_head )); then
    committed_head="$live_head"
    origin=working-tree
  fi
  if [[ ! "$source_head" =~ ^[0-9]+$ ]]; then
    log "stale receipt copy refused: source head ${source_head:-missing} is behind committed head $committed_head ($head_values comparison=valid_source)"
    return 1
  fi
  if (( 10#$source_head > 10#$committed_head )); then
    log "stale receipt copy refused: source head $source_head is ahead of committed head $committed_head ($head_values comparison=source>max(live,committed))"
    return 1
  fi
  (( 10#$source_head < 10#$committed_head )) || return 0

  replacement="$(mktemp -d "$(dirname "$source")/.receipt-adopt.XXXXXX")" || return 1
  if [[ "$origin" == HEAD ]]; then
    if ! git_repo archive "$committed_commit" observation-receipts | tar -x -C "$replacement"; then
      rm -rf -- "$replacement"
      log "stale receipt copy refused: could not read committed receipt tree ($head_values comparison=source<committed)"
      return 1
    fi
  elif ! cp -a -- "$repo/observation-receipts" "$replacement/observation-receipts"; then
    rm -rf -- "$replacement"
    log "stale receipt copy refused: could not read working receipt tree ($head_values comparison=source<live)"
    return 1
  fi
  if [[ ! -f "$replacement/observation-receipts/chain_head.json" ]]; then
    rm -rf -- "$replacement"
    log "stale receipt copy refused: adopted receipt tree has no chain head ($head_values comparison=adopted_head_exists)"
    return 1
  fi
  adopted_head="$(jq -r '.sequence_number // empty' "$replacement/observation-receipts/chain_head.json" 2>/dev/null || :)"
  if [[ "$adopted_head" != "$committed_head" ]]; then
    rm -rf -- "$replacement"
    log "stale receipt copy refused: adopted receipt head changed during copy ($head_values comparison=adopted_head)"
    return 1
  fi
  path_count="$(find "$replacement/observation-receipts" -type f | wc -l)"
  if ! rm -rf -- "$source" || ! mv -- "$replacement/observation-receipts" "$source"; then
    rm -rf -- "$replacement"
    log "stale receipt copy refused: could not install committed receipt tree ($head_values comparison=install_adopted_tree)"
    return 1
  fi
  rmdir -- "$replacement" || return 1
  log "adopted committed receipt chain: source head $source_head, committed head $committed_head, paths adopted $path_count ($origin)"
  return 0
}

stage_artifacts() {
  local target candidate

  if [[ -f "$run_dir/.handoff/READY" ]]; then
    # Journal before allocation: even a kill at mkdir cannot strand an unnamed
    # transaction tree every five minutes. Never adopt an unjournalled tree.
    candidate="$repo/.datapulse-publish.spool"
    [[ ! -e "$candidate" && ! -L "$candidate" ]] \
      || die 'publish staging refused: unaccounted spool transaction tree'
    publish_root="$candidate"
    record_spool_transaction
    mkdir "$publish_root"
  else
    publish_root="$(mktemp -d "$repo/.datapulse-publish.XXXXXX")"
  fi
  publish_root_owned=true
  mkdir -p "$publish_root/new" "$publish_root/backup"
  for target in "${MANAGED_ARTIFACT_PATHS[@]}"; do
    [[ -e "$run_dir/$target" ]] || die "publish staging failed: missing $target"
    if [[ "$target" == observation-receipts ]] && ! refuse_stale_receipt_copy "$run_dir/$target"; then
      die "publish staging failed: stale receipt copy"
    fi
    mkdir -p "$(dirname "$publish_root/new/$target")"
    cp -a "$run_dir/$target" "$publish_root/new/$target"
  done
}

# Deferred cycles leave generated files in the live checkout. Seed the next
# frozen run from those bytes before generators update them, including files
# that a later generator does not rewrite on every cycle.
seed_buffered_artifacts() {
  local target

  [[ "$(sed -n '2p' "$(publication_state_path)" 2>/dev/null)" == buffered=1 ]] \
    || return 0
  for target in "${MANAGED_ARTIFACT_PATHS[@]}"; do
    [[ -e "$repo/$target" ]] || continue
    rm -rf -- "$run_dir/$target"
    mkdir -p -- "$(dirname -- "$run_dir/$target")"
    cp -a -- "$repo/$target" "$run_dir/$target"
  done
}

swap_artifact() {
  local target="$1"

  if [[ "$target" == observation-receipts ]] && ! refuse_stale_receipt_copy "$publish_root/new/$target"; then
    die "publish swap failed: stale receipt copy"
  fi
  swapped_paths+=("$target")
  if [[ -e "$repo/$target" ]]; then
    mkdir -p "$(dirname "$publish_root/backup/$target")"
    mv "$repo/$target" "$publish_root/backup/$target"
    old_target_moved["$target"]=true
  fi
  mkdir -p "$(dirname "$repo/$target")"
  mv "$publish_root/new/$target" "$repo/$target"
  new_target_moved["$target"]=true
}

swap_artifacts() {
  local target

  publish_swapped=true
  for target in "${ARTIFACT_PATHS[@]}"; do
    swap_artifact "$target"
  done
}

read_mcp_sync_state() {
  local state="${DATAPULSE_MCP_SYNC_STATE:-}"
  local sha=""
  local failures=0
  local line key value

  if [[ -n "$state" && -f "$state" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ "$line" == *=* ]] || continue
      key="${line%%=*}"
      value="${line#*=}"
      case "$key" in
        source_sha256)
          if [[ "$value" =~ ^[0-9a-f]{64}$ ]]; then
            sha="$value"
          fi
          ;;
        consecutive_failures)
          if [[ "$value" == 0 || "$value" =~ ^[1-9][0-9]*$ ]]; then
            failures="$value"
          fi
          ;;
      esac
    done < "$state" || true
  fi
  printf '%s %s\n' "$sha" "$failures"
}

write_mcp_sync_state() {
  local sha="$1"
  local failures="$2"
  local state="${DATAPULSE_MCP_SYNC_STATE:-}"
  local tmp

  if [[ -z "$state" ]]; then
    log "mcp-sync state path unset; continuing health cycle"
    return 0
  fi
  tmp="${state}.tmp"
  if ! mkdir -p -- "$(dirname -- "$state")"; then
    log "mcp-sync state directory could not be created; continuing health cycle"
    return 0
  fi
  if ! printf 'source_sha256=%s\nconsecutive_failures=%s\n' "$sha" "$failures" > "$tmp"; then
    log "mcp-sync state write failed; continuing health cycle"
    rm -f -- "$tmp"
    return 0
  fi
  if ! mv -f -- "$tmp" "$state"; then
    log "mcp-sync state write failed; continuing health cycle"
    rm -f -- "$tmp"
    return 0
  fi
}

# Repeated publish deferrals are a stall, not a transient race, so the count
# must survive cycles: it is persisted in the same key=value, .tmp+mv -f,
# fail-soft shape as the mcp-sync state. The default path sits beside the
# telemetry file so the two travel together. Every failure here logs and
# continues; it must never fail the cycle.
publish_deferral_state_path() {
  local telemetry_path

  if [[ -n "${DATAPULSE_PUBLISH_DEFERRAL_STATE:-}" ]]; then
    printf '%s\n' "$DATAPULSE_PUBLISH_DEFERRAL_STATE"
    return 0
  fi
  telemetry_path="${DATAPULSE_TELEMETRY_FILE:-${telemetry_file:-}}"
  if [[ -n "$telemetry_path" ]]; then
    printf '%s\n' "$(dirname -- "$telemetry_path")/publish-deferrals.state"
    return 0
  fi
  return 1
}

read_publish_deferral_state() {
  local state reason="" count=0 line key value

  state="$(publish_deferral_state_path || :)"
  if [[ -n "$state" && -f "$state" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ "$line" == *=* ]] || continue
      key="${line%%=*}"
      value="${line#*=}"
      case "$key" in
        reason) reason="$value" ;;
        consecutive_deferrals)
          if [[ "$value" == 0 || "$value" =~ ^[1-9][0-9]*$ ]]; then
            count="$value"
          fi
          ;;
      esac
    done < "$state" || true
  fi
  # Tab-separated: a reason is a human sentence that can contain spaces, unlike
  # the two opaque tokens mcp-sync joins with a space.
  printf '%s\t%s\n' "$reason" "$count"
}

write_publish_deferral_state() {
  local reason="$1"
  local count="$2"
  local state tmp

  state="$(publish_deferral_state_path || :)"
  if [[ -z "$state" ]]; then
    log "publish deferral state path unavailable; continuing health cycle"
    return 0
  fi
  tmp="${state}.tmp"
  if ! mkdir -p -- "$(dirname -- "$state")"; then
    log "publish deferral state directory could not be created; continuing health cycle"
    return 0
  fi
  if ! printf 'reason=%s\nconsecutive_deferrals=%s\n' "$reason" "$count" > "$tmp"; then
    log "publish deferral state write failed; continuing health cycle"
    rm -f -- "$tmp"
    return 0
  fi
  if ! mv -f -- "$tmp" "$state"; then
    log "publish deferral state write failed; continuing health cycle"
    rm -f -- "$tmp"
    return 0
  fi
}

clear_publish_deferral_state() {
  write_publish_deferral_state "" 0
}

# One publish deferral: increment the counter for this reason (a new reason
# starts at 1), persist it, escalate exactly once when it first reaches the
# threshold, and carry the count on the existing publish stage telemetry row.
# The reason is the stable phrase, never the die message's changing hashes, so
# the same stall accumulates instead of resetting every cycle. This only
# records; apply_publish_deferral below decides the cycle's exit status.
note_publish_deferral() {
  local reason="$1"
  local state_line stored_reason count threshold elapsed_ms extra now_ms

  state_line="$(read_publish_deferral_state)"
  stored_reason="${state_line%%$'\t'*}"
  count="${state_line#*$'\t'}"
  if [[ "$stored_reason" == "$reason" && "$count" =~ ^[0-9]+$ && "$count" -gt 0 ]]; then
    count=$((count + 1))
  else
    count=1
  fi
  write_publish_deferral_state "$reason" "$count"

  threshold="${DATAPULSE_PUBLISH_DEFERRAL_ALERT_THRESHOLD:-$DEFAULT_PUBLISH_DEFERRAL_ALERT_THRESHOLD}"
  if ! [[ "$threshold" =~ ^[1-9][0-9]*$ ]]; then
    threshold="$DEFAULT_PUBLISH_DEFERRAL_ALERT_THRESHOLD"
  fi
  if (( count == threshold )); then
    log "publish deferred ${count} cycles in a row: ${reason}"
  fi

  now_ms="$(milliseconds)"
  elapsed_ms="$(( now_ms - ${cycle_started:-$now_ms} ))"
  extra="$(jq -nc --arg reason "$reason" --argjson n "$count" \
    '{reason:$reason, consecutive_deferrals:$n, non_fatal:true}' 2>/dev/null || :)"
  telemetry publish "$elapsed_ms" skipped "$extra"
}

# True once the persisted consecutive-deferral count has reached the alert
# threshold. The count is the one note_publish_deferral writes, so it persists
# across cycles and the exit status follows it rather than a single race.
publish_deferral_exhausted() {
  local state_line count threshold

  state_line="$(read_publish_deferral_state)"
  count="${state_line#*$'\t'}"
  threshold="${DATAPULSE_PUBLISH_DEFERRAL_ALERT_THRESHOLD:-$DEFAULT_PUBLISH_DEFERRAL_ALERT_THRESHOLD}"
  [[ "$threshold" =~ ^[1-9][0-9]*$ ]] \
    || threshold="$DEFAULT_PUBLISH_DEFERRAL_ALERT_THRESHOLD"
  [[ "$count" =~ ^[0-9]+$ ]] || return 1
  (( count >= threshold ))
}

# Record a publish deferral and end the cycle. A skipped cycle exits 0 and keeps
# non_fatal:true telemetry, matching what the code already declares; only a
# sustained stall -- the count reaching the threshold -- dies, so a persistent
# stall, not a transient race, is what turns the unit red.
apply_publish_deferral() {
  local reason="$1" message="$2"

  note_publish_deferral "$reason"
  if publish_deferral_exhausted; then
    die "$message"
  fi
  log "$message"
  exit 0
}

run_mcp_sync() {
  local stage_started result_file result result_line rc
  local source_sha state_line state_sha state_failures
  local max_failures new_failures
  local source_line source_commit source_date
  local -a sync_args

  stage_started="$(milliseconds)"
  result_file="$run_dir/.mcp-sync-result"
  source_sha="$(sha256sum "$run_dir/mcp/server.py" | awk '{print $1}')"
  max_failures="${DATAPULSE_MCP_SYNC_MAX_FAILURES:-3}"
  if ! [[ "$max_failures" =~ ^[1-9][0-9]*$ ]]; then
    log "warning: DATAPULSE_MCP_SYNC_MAX_FAILURES is not a positive integer; falling back to 3"
    max_failures=3
  fi

  state_line="$(read_mcp_sync_state)"
  state_sha="${state_line%% *}"
  state_failures="${state_line#* }"
  if ! [[ "$state_failures" == 0 || "$state_failures" =~ ^[1-9][0-9]*$ ]]; then
    state_failures=0
  fi

  if [[ "$state_sha" == "$source_sha" && "$state_failures" -ge "$max_failures" ]]; then
    telemetry mcp-sync 0 fail \
      "{\"result\":\"skipped\",\"reason\":\"circuit_open\",\"consecutive_failures\":${state_failures},\"source_sha\":\"${source_sha}\",\"non_fatal\":false}"
    log "mcp-sync installer circuit open (source_sha=${source_sha:0:7} consecutive_failures=${state_failures} threshold=${max_failures}); failing health cycle"
    return 1
  fi

  # The frozen snapshot lives in a scratch mktemp dir, so the sync script
  # cannot resolve a commit from --source alone and refuses to run without
  # an advertised sha. The snapshot is a byte copy of the checkout's
  # mcp/server.py, so its identity is the last commit that touched that
  # path in the checkout the stage reads ($repo via git_repo) -- not HEAD:
  # every health cycle commits artifacts (chore(health): ...), so HEAD
  # advanced every few minutes while the served server.py stayed
  # byte-identical, the marker changed under the sync, and it redeployed
  # and restarted an unchanged server each cycle. The rule is
  # deliberately path-based, never message-based, so the next timer-driven
  # generator cannot reintroduce it. The override is all-or-nothing: the
  # sync script refuses a sha without a date, both values come from one
  # git log line so they describe a single revision, and an empty or
  # unresolved value must never reach the marker defaults (a literal HEAD
  # would look valid). If the path has no history (untracked server.py,
  # or a checkout where mcp/ was removed), the lookup returns nothing and
  # the stage passes no sha at all: falling back to HEAD would restore
  # the redeploy loop, so the sync script's own typed failure plus this
  # circuit breaker stay the honest signal. A failed installer is fatal:
  # the publisher must not report a successful cycle while the running MCP
  # server still serves the previous source.
  source_line="$(git_repo log -1 --format='%H %cs' "${source_snapshot:-HEAD}" -- mcp/server.py 2>/dev/null || :)"
  source_commit="${source_line%% *}"
  source_date="${source_line#* }"
  sync_args=(--source "$run_dir/mcp/server.py" --result-file "$result_file")
  if [[ "$source_commit" =~ ^[0-9a-f]{40,64}$ && "$source_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    sync_args+=(--source-sha "$source_commit" --source-date "$source_date")
  else
    log "mcp-sync source commit unavailable; continuing without advertised commit"
  fi

  log "mcp-sync started from frozen snapshot $run_dir/mcp/server.py"
  if "$MCP_SYNC_SCRIPT" "${sync_args[@]}"; then
    result=unknown
    result_line=""
    [[ ! -f "$result_file" ]] || result_line="$(<"$result_file")"
    result="${result_line%%[[:space:]]*}"
    case "$result" in
      no-change|deployed) ;;
      *) result=unknown ;;
    esac
    write_mcp_sync_state "$source_sha" 0
    telemetry mcp-sync "$(( $(milliseconds) - stage_started ))" success \
      "{\"result\":\"$result\",\"result_line\":\"$result_line\"}"
    log "mcp-sync complete; result=$result"
    return 0
  else
    rc=$?
  fi

  if [[ "$state_sha" == "$source_sha" ]]; then
    new_failures=$((state_failures + 1))
  else
    new_failures=1
  fi
  write_mcp_sync_state "$source_sha" "$new_failures"

  telemetry mcp-sync "$(( $(milliseconds) - stage_started ))" fail "{\"non_fatal\":false,\"exit_code\":$rc,\"consecutive_failures\":$new_failures}"
  log "mcp-sync installer failed (exit $rc); failing health cycle"
  return "$rc"
}

# Observation-time signing. The host that observes also signs: the health
# artifact it just produced is signed into observation-receipts/ AFTER the
# existing cycle has staged, swapped and COMMITTED it, so the receipt can name
# the commit that carries the very bytes it binds (--artifact-commit). The
# signed health is the probe artifact, before the pipeline stamps its per-cycle
# liveness heartbeat; the signer normalizes that heartbeat out of the digest, so
# an unchanged observation still reports already_signed. The stage is
# deliberately non-fatal -- a missing key, a missing signer, a digest mismatch
# or a failed receipt commit must never turn a read-only evidence problem into a
# health-data outage -- but never silent: a failure emits telemetry and one
# warning line. No key material is read, logged, or serialized here.
#
# The closed telemetry vocabulary (check_heartbeat.py STAGES) has no
# observation-sign root and this lane must not edit the product checkout, so
# the failure is recorded as the accepted observation-capture.sign sub-stage
# with the logical event name carried in extra.event.
observation_signing_failure() {
  local stage_started="$1" reason="$2" extra_json

  extra_json="$(jq -cn --arg reason "$reason" '{event:"observation_sign",reason:$reason,non_fatal:true}' 2>/dev/null)" \
    || extra_json='{"event":"observation_sign","reason":"unspecified","non_fatal":true}'
  telemetry observation-capture.sign "$(( $(milliseconds) - stage_started ))" fail "$extra_json"
  log "warning: observation receipt signing failed: $reason; continuing health cycle"
}

# Seed the run-dir receipts from the live checkout. The run dir is a fresh
# mktemp -d each cycle, so without this the signer restarts the chain at
# sequence_number 1 and writes a one-entry day file, which stage_artifacts()
# would then swap over the accumulated chain. Returns non-zero on failure and
# never logs key material.
seed_observation_receipts() {
  local output_root="$1"

  mkdir -p "$output_root" 2>/dev/null || return 1
  if [[ -d "$repo/observation-receipts" ]]; then
    cp -a "$repo/observation-receipts/." "$output_root/" 2>/dev/null || return 1
  fi
  return 0
}

# observation-receipts/ is a managed artifact, so stage_artifacts() requires the
# path to exist even before the signer runs. Create it and seed it from the live
# checkout before staging, so the artifact commit's swap is a no-op for the
# accumulated chain; a seeding failure is reported but never fatal.
prepare_observation_receipts() {
  local stage_started="$1"

  if ! seed_observation_receipts "$run_dir/observation-receipts"; then
    observation_signing_failure "$stage_started" "seed_failed"
  fi
  return 0
}

# Undo an in-flight receipt stage/commit so a failure cannot leave a managed
# path dirty for the next cycle's assert_artifacts_clean(). clean -fd removes a
# first-ever receipt that git did not yet track; checkout repairs a tracked one.
restore_observation_receipts() {
  git_repo restore --staged -- observation-receipts >/dev/null 2>&1 || :
  git_repo checkout -- observation-receipts >/dev/null 2>&1 || :
  git_repo clean -fd -- observation-receipts >/dev/null 2>&1 || :
}

# Receipt publication cadence. The Cloudflare Pages deploy triggers on
# observation-receipts/** only -- the health commits touch health/**, which the
# workflow's paths: allowlist ignores -- so the deploy cadence is the receipt
# commit cadence. Probing, health publication and signing stay on the
# five-minute tick; only the receipts-only commit is held back to this
# interval. The signer still runs every cycle and still binds an artifact commit
# -- the newest already-published one, because a commit that cycle pushed is not
# yet merged or materialized; the signed chain accumulates in a gitignored
# pending directory until the tick, so a per-cycle health commit cannot sweep a
# receipt in early and no push can carry one before it is due.
#
# State file (last publish timestamp, epoch seconds):
#   ${DATAPULSE_RECEIPT_PUBLISH_STATE:-$repo/var/log/receipt-publish-state}
# Pending signed chain between ticks:
#   ${DATAPULSE_RECEIPT_PUBLISH_PENDING:-$repo/var/observation-receipts-pending}
# Interval:
#   DATAPULSE_RECEIPT_PUBLISH_INTERVAL_SECONDS (default 1800 = 30 minutes)
readonly DEFAULT_RECEIPT_PUBLISH_INTERVAL_SECONDS=1800

receipt_publish_state_file() {
  printf '%s\n' "${DATAPULSE_RECEIPT_PUBLISH_STATE:-$repo/var/log/receipt-publish-state}"
}

receipt_publish_pending_dir() {
  printf '%s\n' "${DATAPULSE_RECEIPT_PUBLISH_PENDING:-$repo/var/observation-receipts-pending}"
}

receipt_publish_interval_seconds() {
  local interval="${DATAPULSE_RECEIPT_PUBLISH_INTERVAL_SECONDS:-${DEFAULT_RECEIPT_PUBLISH_INTERVAL_SECONDS:-1800}}"

  if [[ ! "$interval" =~ ^[0-9]+$ ]]; then
    log "warning: DATAPULSE_RECEIPT_PUBLISH_INTERVAL_SECONDS is not a non-negative integer; falling back to ${DEFAULT_RECEIPT_PUBLISH_INTERVAL_SECONDS:-1800}"
    interval="${DEFAULT_RECEIPT_PUBLISH_INTERVAL_SECONDS:-1800}"
  fi
  printf '%s\n' "$interval"
}

# A missing or unreadable state means "publish now": that preserves the
# pre-change first-cycle behaviour, keeps --preflight-style fixtures that never
# write a state file committing immediately, and fails open (publish) rather
# than freezing the chain if the state cannot be trusted.
receipt_publish_due() {
  local state last interval now

  state="$(receipt_publish_state_file)"
  interval="$(receipt_publish_interval_seconds)"
  [[ -f "$state" ]] || return 0
  last="$(<"$state")"
  if [[ ! "$last" =~ ^[0-9]+$ ]]; then
    log "warning: receipt publish state is unreadable ($state); publishing now"
    return 0
  fi
  now="$(date +%s)"
  (( now - last >= interval ))
}

receipt_publish_mark() {
  local state now tmp

  state="$(receipt_publish_state_file)"
  now="$(date +%s)"
  if ! mkdir -p "$(dirname "$state")" 2>/dev/null; then
    log "warning: receipt publish state directory could not be created; receipts may publish early"
    return 0
  fi
  tmp="${state}.tmp.$$"
  if printf '%s\n' "$now" > "$tmp" && mv -f -- "$tmp" "$state"; then
    return 0
  fi
  rm -f -- "$tmp"
  log "warning: receipt publish state could not be written; receipts may publish early"
  return 0
}

# OKF bundle refresh cadence. The bundle under docs/okf is a served projection
# of the health snapshot: every dataset document is rendered from
# health/latest.json (with datapulse.json and changelog.json), so it must be
# regenerated on the same schedule that moves the snapshot. Nothing regenerated
# it before this stage, and the committed projection drifted a fortnight behind
# the health data it described. Generation costs five to eight minutes, which
# cannot ride every five-minute tick inside the service's 25-minute
# TimeoutStartSec, so the refresh is gated to a daily interval: the bundle's own
# generated.at is derived from its input snapshot, and a day bounds how stale
# the published projection can be without spending the generator's runtime on
# every tick.
#
# State file (last successful refresh timestamp, epoch seconds):
#   ${DATAPULSE_OKF_REFRESH_STATE:-$repo/var/log/okf-refresh-state}
# Interval:
#   DATAPULSE_OKF_REFRESH_INTERVAL_SECONDS (default 86400 = 1 day)
readonly DEFAULT_OKF_REFRESH_INTERVAL_SECONDS=86400

okf_refresh_state_file() {
  printf '%s\n' "${DATAPULSE_OKF_REFRESH_STATE:-$repo/var/log/okf-refresh-state}"
}

okf_refresh_interval_seconds() {
  local interval="${DATAPULSE_OKF_REFRESH_INTERVAL_SECONDS:-${DEFAULT_OKF_REFRESH_INTERVAL_SECONDS:-86400}}"

  if [[ ! "$interval" =~ ^[0-9]+$ ]]; then
    log "warning: DATAPULSE_OKF_REFRESH_INTERVAL_SECONDS is not a non-negative integer; falling back to ${DEFAULT_OKF_REFRESH_INTERVAL_SECONDS:-86400}"
    interval="${DEFAULT_OKF_REFRESH_INTERVAL_SECONDS:-86400}"
  fi
  printf '%s\n' "$interval"
}

# A missing or unreadable state means "refresh now": that preserves the
# first-cycle behaviour (the very first run must publish a bundle), lets
# fixtures that never write a state file refresh immediately, and fails open
# rather than freezing the projection forever if the state cannot be trusted.
# Mirrors receipt_publish_due().
okf_refresh_due() {
  local state last interval now

  state="$(okf_refresh_state_file)"
  interval="$(okf_refresh_interval_seconds)"
  [[ -f "$state" ]] || return 0
  last="$(<"$state")"
  if [[ ! "$last" =~ ^[0-9]+$ ]]; then
    log "warning: okf refresh state is unreadable ($state); refreshing now"
    return 0
  fi
  now="$(date +%s)"
  (( now - last >= interval ))
}

okf_refresh_mark() {
  local state now tmp

  state="$(okf_refresh_state_file)"
  now="$(date +%s)"
  if ! mkdir -p "$(dirname "$state")" 2>/dev/null; then
    log "warning: okf refresh state directory could not be created; bundle may refresh again next tick"
    return 0
  fi
  tmp="${state}.tmp.$$"
  if printf '%s\n' "$now" > "$tmp" && mv -f -- "$tmp" "$state"; then
    return 0
  fi
  rm -f -- "$tmp"
  log "warning: okf refresh state could not be written; bundle may refresh again next tick"
  return 0
}

# Refresh the published OKF bundle only when the daily gate says it is due, and
# write it into the run dir's docs/okf so the existing stage/swap/commit path
# publishes it with the health snapshot it projects. Deliberately non-fatal, in
# the same shape as the mcp-sync and observation-capture stages: the probe cycle
# produces the health data and the bundle is only a projection of it, so a
# broken generator must never stop the pipeline that feeds it. The state is
# recorded only after a successful generation, so a failed run is retried on
# the next tick instead of being skipped for the whole interval.
#
# The telemetry stage root is the closed "deltas" vocabulary (this lane must not
# edit the product checkout), with gen_okf_bundle as the sub-stage that names
# the generator.
run_okf_refresh() {
  local stage_started rc output line

  stage_started="$(milliseconds)"

  if ! okf_refresh_due; then
    log "okf bundle refresh not due; keeping the committed projection"
    telemetry deltas.gen_okf_bundle 0 skipped '{"reason":"interval_not_elapsed"}'
    return 0
  fi

  log "okf bundle refresh started"
  if output="$("$PYTHON_BIN" "$run_dir/scripts/gen_okf_bundle.py" 2>&1)"; then
    rc=0
  else
    rc=$?
  fi
  if [[ -n "$output" ]]; then
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      log "okf bundle: $line"
    done <<< "$output"
  fi

  if (( rc == 0 )) && [[ -d "$run_dir/docs/okf" ]]; then
    okf_refresh_mark
    telemetry deltas.gen_okf_bundle "$(( $(milliseconds) - stage_started ))" success
    log "okf bundle refreshed at docs/okf"
    return 0
  fi

  if (( rc == 0 )); then
    rc=1
    log "okf bundle generator exited 0 but wrote no docs/okf"
  fi
  telemetry deltas.gen_okf_bundle "$(( $(milliseconds) - stage_started ))" fail \
    "{\"non_fatal\":true,\"exit_code\":$rc}"
  log "warning: okf bundle generation failed (exit $rc); continuing health cycle"
  return 0
}

# Overlay the accumulated pending chain on the committed chain the signer is
# seeded with, and only when the pending head is strictly newer. A stale or
# partial pending tree must never regress the sequence the signer continues
# from.
seed_pending_receipts() {
  local output_root="$1" pending pending_head committed_head

  pending="$(receipt_publish_pending_dir)"
  [[ -d "$pending" ]] || return 0
  pending_head="$(jq -r '.sequence_number // empty' "$pending/chain_head.json" 2>/dev/null || :)"
  committed_head="$(jq -r '.sequence_number // empty' "$output_root/chain_head.json" 2>/dev/null || :)"
  [[ "$pending_head" =~ ^[0-9]+$ ]] || return 0
  if [[ "$committed_head" =~ ^[0-9]+$ ]] && (( pending_head <= committed_head )); then
    return 0
  fi
  cp -a "$pending/." "$output_root/" 2>/dev/null || return 1
  return 0
}

# Persist the run-dir chain to the gitignored pending directory. Written to a
# sibling temp dir and swapped so an interrupted write cannot leave a partial
# chain for the next cycle's signer. This is pre-commit storage, not a publish
# copy: new signatures must be ahead of HEAD, but must never replace a newer
# live, committed or pending chain. The publish-copy guard runs after commit.
persist_pending_receipts() {
  local pending tmp source_head baseline

  pending="$(receipt_publish_pending_dir)"
  source_head="$(jq -r '.sequence_number // empty' "$run_dir/observation-receipts/chain_head.json" 2>/dev/null || :)"
  [[ "$source_head" =~ ^[0-9]+$ ]] || return 1
  for baseline in \
      "$(jq -r '.sequence_number // empty' "$repo/observation-receipts/chain_head.json" 2>/dev/null || :)" \
      "$(git_repo show HEAD:observation-receipts/chain_head.json 2>/dev/null | jq -r '.sequence_number // empty' 2>/dev/null || :)" \
      "$(if [[ -d "$pending" ]]; then jq -r '.sequence_number // empty' "$pending/chain_head.json" 2>/dev/null || :; else printf '0'; fi)"; do
    if [[ ! "$baseline" =~ ^[0-9]+$ ]] || (( 10#$source_head < 10#$baseline )); then
      log "pending receipt copy refused: source head $source_head would replace newer or unreadable head ${baseline:-missing}"
      return 1
    fi
  done
  if ! mkdir -p "$(dirname "$pending")" 2>/dev/null; then
    log "warning: receipt pending directory could not be created; continuing health cycle"
    return 0
  fi
  tmp="${pending}.tmp.$$"
  rm -rf -- "$tmp"
  if ! mkdir -p "$tmp" 2>/dev/null; then
    log "warning: receipt pending directory could not be created; continuing health cycle"
    return 0
  fi
  if ! cp -a "$run_dir/observation-receipts/." "$tmp/" 2>/dev/null; then
    log "warning: receipt pending copy failed; continuing health cycle"
    rm -rf -- "$tmp"
    return 0
  fi
  rm -rf -- "$pending"
  if ! mv -- "$tmp" "$pending"; then
    log "warning: receipt pending swap failed; continuing health cycle"
    rm -rf -- "$tmp"
    return 0
  fi
  return 0
}

# The signed receipt is a second, receipts-only commit on top of the artifact
# commit. It reuses the pipeline's git wrapper and commit identity and is
# deliberately fail-soft. An isolated index commits the run-dir chain before
# the guarded copy materializes it in the live checkout. A stage or commit
# failure leaves that checkout untouched. The first transaction's rollback is
# single-use, so this stages just the receipt paths instead of re-driving
# stage_artifacts()/swap_artifacts().
#
# This is the only step the publish interval gates. Until the tick the signed
# chain is persisted to the gitignored pending directory and the live checkout
# is left untouched, so the per-cycle health commit (which runs earlier and
# lists observation-receipts in its add set) can never carry a receipt and no
# push can carry one before the interval elapses.
commit_observation_receipts() {
  local stage_started="$1" observed_at="$2" message receipt_index

  if [[ -z "$observed_at" ]]; then
    observation_signing_failure "$stage_started" "missing_observed_at"
    return 0
  fi
  message="$OBSERVATION_COMMIT_PREFIX $observed_at"

  if [[ "$publication_waiting" == true ]]; then
    if ! persist_pending_receipts; then
      observation_signing_failure "$stage_started" "stale_receipt_copy"
      return 0
    fi
    log "observation receipt held while publication is in flight: $message"
    return 0
  fi

  if ! receipt_publish_due; then
    if ! persist_pending_receipts; then
      observation_signing_failure "$stage_started" "stale_receipt_copy"
      return 0
    fi
    log "observation receipt held until the publish interval elapses: $message"
    return 0
  fi

  # Keep the newest chain in the pending directory before touching the live
  # checkout, so a failed stage or commit cannot lose the receipts this tick
  # was meant to publish.
  if ! persist_pending_receipts; then
    observation_signing_failure "$stage_started" "stale_receipt_copy"
    return 0
  fi

  # receipt_copy_ordering: committing through the live tree would require
  # copying an uncommitted head past the publish guard. Stage from the run tree
  # instead, preserving every other HEAD path and the checkout's real index.
  receipt_index="$run_dir/.observation-receipts.index"
  rm -f -- "$receipt_index"
  if ! GIT_INDEX_FILE="$receipt_index" git_repo read-tree HEAD >/dev/null 2>&1 \
      || ! GIT_INDEX_FILE="$receipt_index" git_repo --work-tree="$run_dir" \
        add -A -- observation-receipts >/dev/null 2>&1; then
    rm -f -- "$receipt_index"
    observation_signing_failure "$stage_started" "receipt_stage_failed"
    return 0
  fi
  if GIT_INDEX_FILE="$receipt_index" git_repo diff --cached --quiet -- observation-receipts; then
    rm -f -- "$receipt_index"
    # A due tick with nothing new (already_signed and no earlier receipt
    # waiting) still arms the next interval so the cadence stays on a stable
    # grid instead of publishing the next change immediately.
    receipt_publish_mark
    log "observation receipt unchanged; nothing to publish"
    return 0
  fi
  if ! GIT_INDEX_FILE="$receipt_index" git_repo --work-tree="$run_dir" \
      -c user.name="Redza Halim" -c user.email="r3dz4r@gmail.com" \
      commit -m "$message" >/dev/null 2>&1; then
    rm -f -- "$receipt_index"
    observation_signing_failure "$stage_started" "receipt_commit_failed"
    return 0
  fi
  rm -f -- "$receipt_index"

  if ! refuse_stale_receipt_copy "$run_dir/observation-receipts"; then
    observation_signing_failure "$stage_started" "stale_receipt_copy"
    return 0
  fi
  if ! git_repo_index_retry restore --source=HEAD --staged --worktree -- observation-receipts >/dev/null 2>&1; then
    observation_signing_failure "$stage_started" "receipt_stage_failed"
    return 0
  fi
  receipt_publish_mark
  log "observation receipt committed: $message"
  return 0
}

run_observation_signing() {
  local stage_started signer published_health_path output_root stderr_file
  local sign_output status receipt_id sequence_number observed_at rc reason
  local published_commit published_now
  local -a signer_args

  stage_started="$(milliseconds)"
  signer="$repo/scripts/observation_receipt.py"
  published_health_path="$run_dir/health/latest.published.json"
  output_root="$run_dir/observation-receipts"

  # Seed from the live checkout before signing so the signer sees the
  # accumulated chain; a seeding failure is reported like the other signing
  # failures and the signer is not invoked.
  if ! seed_observation_receipts "$output_root"; then
    observation_signing_failure "$stage_started" "seed_failed"
    return 0
  fi
  # Receipts signed since the last publish tick live only in the pending
  # directory; hand them to the signer so the chain it continues is complete
  # and the due tick can commit every held receipt in one commit.
  if ! seed_pending_receipts "$output_root"; then
    observation_signing_failure "$stage_started" "seed_failed"
    return 0
  fi

  if [[ ! -f "$signer" ]]; then
    observation_signing_failure "$stage_started" "signer_missing"
    return 0
  fi

  # Resolve the newest ALREADY-PUBLISHED artifact commit, P, from the head of
  # refs/remotes/origin/main as this cycle's preflight fetched it. The commit
  # push_head() just made is deliberately not signed: the signer accepts only a
  # commit the published mirror has materialized, the mirror materializes only
  # the source repository's refs/heads/main, and the health-automation merge that
  # lands a fresh commit has not run yet -- so signing HEAD is refused
  # permanently. Read the ref itself: push_head() reassigns fetched_origin to
  # HEAD on a successful push, so $fetched_origin is the unpublished commit
  # again by signing time. Deliberately do not re-fetch here: the preflight fetch
  # is at least one cycle old, which is what makes P already merged and
  # materialized rather than a race against the merge workflow.
  if ! published_commit="$(git_repo rev-parse --verify refs/remotes/origin/main 2>/dev/null)"; then
    observation_signing_failure "$stage_started" "published_commit_unavailable"
    return 0
  fi

  # Materialize P's artifact bytes; the receipt must describe the bytes of the
  # commit it names, so the signer is handed these bytes -- never the staged
  # working-tree snapshot, whose digest would not match P in the mirror.
  if ! git_repo show "$published_commit:health/latest.json" > "$published_health_path" 2>/dev/null; then
    rm -f -- "$published_health_path"
    observation_signing_failure "$stage_started" "published_commit_unavailable"
    return 0
  fi

  # Replaces the staged-vs-live digest guard. The receipt now describes the
  # artifact that IS published, so the guard verifies that the published ref has
  # not moved under the materialization and that the bytes handed to the signer
  # are still P's artifact bytes, read back from P independently. It is a real
  # check, not a deletion: a ref race or a wrong/partial materialization skips
  # signing rather than binding bytes the receipt does not describe.
  published_now="$(git_repo rev-parse --verify refs/remotes/origin/main 2>/dev/null)" || published_now=""
  if [[ "$published_now" != "$published_commit" ]]; then
    observation_signing_failure "$stage_started" "published_commit_moved"
    return 0
  fi
  if ! git_repo show "$published_commit:health/latest.json" 2>/dev/null \
      | cmp -s - "$published_health_path"; then
    observation_signing_failure "$stage_started" "published_artifact_mismatch"
    return 0
  fi

  stderr_file="$run_dir/.observation-signing.stderr"
  signer_args=(
    --output-root "$output_root"
    --health "$published_health_path"
    --signer-socket "$OBSERVATION_SIGNER_SOCKET"
    --registry "$OBSERVATION_REGISTRY"
    --artifact-commit "$published_commit"
    --artifact-path "health/latest.json"
  )
  if sign_output="$(timeout "$OBSERVATION_SIGN_TIMEOUT_SECONDS" "$PYTHON_BIN" "$signer" "${signer_args[@]}" 2>"$stderr_file")"; then
    rc=0
  else
    rc=$?
  fi

  if (( rc != 0 )); then
    reason="signer_exit_${rc}"
    if [[ -s "$stderr_file" ]]; then
      reason="$(tr '\n' ' ' < "$stderr_file" | cut -c1-500)"
    fi
    observation_signing_failure "$stage_started" "$reason"
    return 0
  fi

  status="$(printf '%s' "$sign_output" | jq -er '.status' 2>/dev/null)" || status=""
  case "$status" in
    signed)
      receipt_id="$(printf '%s' "$sign_output" | jq -r '.receipt_id // empty' 2>/dev/null || :)"
      sequence_number="$(printf '%s' "$sign_output" | jq -r '.sequence_number // empty' 2>/dev/null || :)"
      observed_at="$(printf '%s' "$sign_output" | jq -r '.observed_at // empty' 2>/dev/null || :)"
      log "observation receipt signed: receipt_id=${receipt_id} sequence_number=${sequence_number}"
      commit_observation_receipts "$stage_started" "$observed_at"
      ;;
    already_signed)
      # The normal case: the observed digest is unchanged and the signer wrote
      # nothing. The run dir was still seeded with the accumulated chain, so a
      # due tick publishes the receipts that earlier cycles held back instead of
      # waiting for the next change.
      observed_at="$(printf '%s' "$sign_output" | jq -r '.observed_at // empty' 2>/dev/null || :)"
      [[ -n "$observed_at" ]] || observed_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
      commit_observation_receipts "$stage_started" "$observed_at"
      ;;
    *)
      observation_signing_failure "$stage_started" "unparseable_output"
      ;;
  esac
  return 0
}

# Historical-observation capture (the Phase 2 store's only writer). The pilot
# driver has a per-dataset cadence gate, so it is safe to invoke every cycle
# and cheap on most of them; without this call the store holds only the one
# hand-captured observation. The stage is deliberately non-fatal and loud: a
# capture problem must never fail the health cycle (a read-only measurement
# outage must not become a health-data outage), but it is never silent --
# driver output, telemetry and the exit code all reach the pipeline log, so
# a stage capturing nothing cannot look green for weeks.
run_observation_capture() {
  local stage_started store_root timeout_seconds capture_output rc line
  local -a pilot_args

  stage_started="$(milliseconds)"
  store_root="${DATAPULSE_OBSERVATION_STORE:-${HOME}/runtime/datapulse-observations}"
  timeout_seconds="${DATAPULSE_OBSERVATION_CAPTURE_TIMEOUT_SECONDS:-300}"
  if ! [[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
    log "warning: DATAPULSE_OBSERVATION_CAPTURE_TIMEOUT_SECONDS is not a positive integer; falling back to 300"
    timeout_seconds=300
  fi

  if [[ ! -f "$repo/scripts/observation_pilot.py" ]]; then
    log "observation pilot missing from checkout; continuing health cycle"
    telemetry observation-capture 0 skipped '{"reason":"driver_missing"}'
    return 0
  fi

  pilot_args=("$repo/scripts/observation_pilot.py" --store "$store_root" --allow-production-store)

  log "observation capture started; store=$store_root timeout=${timeout_seconds}s"
  if capture_output="$(timeout "$timeout_seconds" "$PYTHON_BIN" "${pilot_args[@]}" 2>&1)"; then
    rc=0
  else
    rc=$?
  fi

  # The driver's own lines are the only place a capture, a cadence skip or a
  # store refusal is explained; surface every line instead of swallowing it.
  if [[ -n "$capture_output" ]]; then
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      log "observation capture: $line"
    done <<< "$capture_output"
  fi

  if (( rc == 0 )); then
    telemetry observation-capture "$(( $(milliseconds) - stage_started ))" success "{\"store\":\"$store_root\"}"
    log "observation capture complete; store=$store_root"
    return 0
  fi

  telemetry observation-capture "$(( $(milliseconds) - stage_started ))" fail \
    "{\"non_fatal\":true,\"exit_code\":$rc}"
  log "observation capture failed (exit $rc); continuing health cycle"
  return 0
}

run_shadow_health_publication() {
  local shadow_file shadow_output managed_path health_commit

  [[ -f "$run_dir/scripts/shadow_health_publication.py" ]] || return 0

  shadow_file="${DATAPULSE_SHADOW_HEALTH_FILE:-$repo/var/log/shadow-health-latest.json}"
  shadow_output="$(realpath -m -- "$shadow_file" 2>/dev/null)" || {
    log "shadow health comparison failed; continuing health cycle"
    return 0
  }
  for managed_path in "${MANAGED_ARTIFACT_PATHS[@]}"; do
    if ! managed_path="$(realpath -m -- "$repo/$managed_path" 2>/dev/null)"; then
      log "shadow health comparison failed; continuing health cycle"
      return 0
    fi
    if [[ "$shadow_output" == "$managed_path" || "$shadow_output" == "$managed_path"/* ]]; then
      log "shadow health comparison failed; continuing health cycle"
      return 0
    fi
  done

  if ! mkdir -p "$(dirname "$shadow_file")" >/dev/null 2>&1; then
    log "shadow health comparison failed; continuing health cycle"
    return 0
  fi

  if ! health_commit="$(git_repo rev-parse HEAD 2>/dev/null)"; then
    log "shadow health comparison failed; continuing health cycle"
    return 0
  fi
  if ! "$PYTHON_BIN" "$run_dir/scripts/shadow_health_publication.py" create \
      --health "$repo/health/latest.json" \
      --output "$shadow_file" \
      --source-commit "${source_snapshot:-$snapshot}" \
      --health-commit "$health_commit" >/dev/null 2>&1; then
    log "shadow health comparison failed; continuing health cycle"
    return 0
  fi
  if ! "$PYTHON_BIN" "$run_dir/scripts/shadow_health_publication.py" compare \
      --health "$repo/health/latest.json" \
      --envelope "$shadow_file" \
      --source-commit "${source_snapshot:-$snapshot}" \
      --health-commit "$health_commit" >/dev/null 2>&1; then
    log "shadow health comparison failed; continuing health cycle"
    return 0
  fi

  log "shadow health equivalent; equivalent=true"
  return 0
}

run_pipeline_receipt() {
  local receipt_file health_commit

  [[ -f "$run_dir/scripts/summarize_pipeline_telemetry.py" ]] || {
    log "pipeline receipt script missing from frozen snapshot; skipping receipt"
    return 0
  }

  receipt_file="${DATAPULSE_RECEIPT_FILE:-$repo/var/log/pipeline-latest.json}"
  health_commit="$(git_repo rev-parse HEAD)"
  if ! mkdir -p "$(dirname "$receipt_file")"; then
    log "pipeline receipt directory could not be created; continuing health cycle"
    return 0
  fi
  if "$PYTHON_BIN" "$run_dir/scripts/summarize_pipeline_telemetry.py" \
      --input "$telemetry_file" \
      --output "$receipt_file" \
      --cycle "$cycle" \
      --mode health-cycle \
      --source-commit "${source_snapshot:-$snapshot}" \
      --health-commit "$health_commit"; then
    log "pipeline receipt written to $receipt_file"
  else
    log "pipeline receipt failed; continuing health cycle"
  fi
  return 0
}

snapshot_shadow_commit() {
  local tree="$1" parent="$2" seq="$3" source="$4" finished_at="$5"
  local -a parent_arg=()
  [[ -z "$parent" ]] || parent_arg=(-p "$parent")
  printf 'chore(health): shadow snapshot\n\nSnapshot-Seq: %s\nSnapshot-Source: %s\nSnapshot-Tree: %s\n' \
    "$seq" "$source" "$tree" | \
    GIT_AUTHOR_DATE="$finished_at" GIT_COMMITTER_DATE="$finished_at" \
      git_repo -c user.name='Redza Halim' -c user.email='r3dz4r@gmail.com' \
        commit-tree "$tree" "${parent_arg[@]}"
}

snapshot_shadow_redact() {
  sed -E \
    -e 's#([[:alpha:]][[:alnum:]+.-]*://)[^/@[:space:]]+@#\1<redacted>@#g' \
    -e 's#([?&](token|password|secret|api[_-]?key)=)[^&[:space:]]+#\1<redacted>#Ig' \
    -e 's#((token|password|secret|api[_-]?key)[=:])[[:graph:]]+#\1<redacted>#Ig'
}

# These values are set by the work function even when a later operation fails.
snapshot_shadow_work() {
  local source="$1" finished_at="$2" scratch index parent='' parent_tree='' parent_seq=0
  local remote_tip message push_error fetch_output update_error attempt
  snapshot_shadow_seq=0 snapshot_shadow_tree='' snapshot_shadow_sha='' snapshot_shadow_reason=''
  if ! scratch="$(mktemp -d /tmp/datapulse-snapshot.XXXXXX)"; then
    snapshot_shadow_reason='temporary index creation failed'
    return 1
  fi
  index="$scratch/index"
  if ! GIT_INDEX_FILE="$index" git_repo read-tree --empty 2>"$scratch/error"; then
    snapshot_shadow_reason="read-tree failed: $(snapshot_shadow_redact < "$scratch/error")"
    rm -rf -- "$scratch"
    return 1
  fi
  if ! git_repo ls-tree -rz HEAD -- "${MANAGED_ARTIFACT_PATHS[@]}" 2>"$scratch/tree-error" | \
      GIT_INDEX_FILE="$index" git_repo update-index -z --index-info 2>"$scratch/error"; then
    snapshot_shadow_reason="managed tree indexing failed: $(snapshot_shadow_redact < "$scratch/tree-error") $(snapshot_shadow_redact < "$scratch/error")"
    rm -rf -- "$scratch"
    return 1
  fi
  if ! snapshot_shadow_tree="$(GIT_INDEX_FILE="$index" git_repo write-tree 2>"$scratch/error")"; then
    snapshot_shadow_reason="write-tree failed: $(snapshot_shadow_redact < "$scratch/error")"
    rm -rf -- "$scratch"
    return 1
  fi
  rm -rf -- "$scratch"

  for attempt in 1 2; do
    # A missing remote ref is the expected first snapshot; other lookup errors fail soft.
    if remote_tip="$(git_repo ls-remote origin refs/heads/health-snapshots 2>&1)"; then
      parent="${remote_tip%%[[:space:]]*}"
    else
      snapshot_shadow_reason="snapshot ref lookup failed: $(printf '%s\n' "$remote_tip" | snapshot_shadow_redact)"
      return 1
    fi
    if [[ -n "$parent" ]]; then
      if ! fetch_output="$(git_repo fetch --no-tags origin \
          refs/heads/health-snapshots:refs/remotes/origin/health-snapshots 2>&1)"; then
        snapshot_shadow_reason="snapshot ref fetch failed: $(printf '%s\n' "$fetch_output" | snapshot_shadow_redact)"
        return 1
      fi
      if ! parent_tree="$(git_repo rev-parse "$parent^{tree}" 2>&1)"; then
        snapshot_shadow_reason="parent tree lookup failed: $(printf '%s\n' "$parent_tree" | snapshot_shadow_redact)"
        return 1
      fi
      if [[ "$snapshot_shadow_tree" == "$parent_tree" ]]; then
        snapshot_shadow_reason='managed tree unchanged'
        return 2
      fi
      if ! message="$(git_repo show -s --format=%B "$parent" 2>&1)"; then
        snapshot_shadow_reason="parent message lookup failed: $(printf '%s\n' "$message" | snapshot_shadow_redact)"
        return 1
      fi
      parent_seq="$(sed -n 's/^Snapshot-Seq: \([0-9][0-9]*\)$/\1/p' <<< "$message")"
      if [[ ! "$parent_seq" =~ ^[0-9]+$ ]]; then
        snapshot_shadow_reason='parent Snapshot-Seq missing or invalid'
        return 1
      fi
    else
      parent_seq=0
    fi
    snapshot_shadow_seq=$((10#$parent_seq + 1))
    if ! snapshot_shadow_sha="$(snapshot_shadow_commit "$snapshot_shadow_tree" "$parent" \
        "$snapshot_shadow_seq" "$source" "$finished_at" 2>&1)"; then
      snapshot_shadow_reason="commit-tree failed: $(printf '%s\n' "$snapshot_shadow_sha" | snapshot_shadow_redact)"
      snapshot_shadow_sha=''
      return 1
    fi
    # Retain the object across GC if the remote refuses the push.
    if ! update_error="$(git_repo update-ref refs/datapulse/health-snapshot-pending "$snapshot_shadow_sha" 2>&1)"; then
      snapshot_shadow_reason="local snapshot retention failed: $(printf '%s\n' "$update_error" | snapshot_shadow_redact)"
      return 1
    fi
    if push_error="$(git_repo push origin \
        "$snapshot_shadow_sha:refs/heads/health-snapshots" 2>&1)"; then
      return 0
    fi
    snapshot_shadow_reason="push rejected: $(printf '%s\n' "$push_error" | snapshot_shadow_redact)"
  done
  return 1
}

run_shadow_snapshot() {
  local started status extra
  started="$(milliseconds)"
  if snapshot_shadow_work "$1" "$2"; then
    status=success
  else
    case $? in
      2) status=skipped ;;
      *) status=failed-nonfatal
         log "warning: snapshot.shadow ${snapshot_shadow_reason}; continuing health cycle" ;;
    esac
  fi
  extra="$(jq -nc --argjson seq "${snapshot_shadow_seq:-0}" \
    --arg tree "${snapshot_shadow_tree:-}" --arg snapshot "${snapshot_shadow_sha:-}" \
    --arg reason "${snapshot_shadow_reason:-}" \
    '{seq:$seq,tree:$tree,snapshot:$snapshot,reason:$reason}')" || return 1
  telemetry snapshot.shadow "$(( $(milliseconds) - started ))" "$status" "$extra"
  return 0
}

# One slot, including abandoned builds and restartable retirement. The sibling
# owner record survives a killed recursive delete. Only the health-lock holder
# may mutate it; metadata is parsed as data, never sourced as shell code.
spool_control() {
  local rc
  local -a deadline=()
  if [[ "$1" == handoff ]]; then
    deadline=(timeout --signal=TERM --kill-after=5s "${SPOOL_HANDOFF_TIMEOUT_SECONDS}s")
  fi
  if "${deadline[@]}" "$PYTHON_BIN" - "$spool_root" "$repo" "$@" <<'PY'
import json
import os
from pathlib import Path
import shutil
import stat
import sys

root, repo = map(Path, sys.argv[1:3])
action, *args = sys.argv[3:]
uid = os.getuid()
root = root.absolute()
if root == Path('/') or root.resolve() != root:
    raise SystemExit('spool refused: root must be a non-symlink absolute directory')
root.mkdir(parents=True, exist_ok=True, mode=0o700)
if root.stat().st_uid != uid or root.stat().st_mode & 0o022:
    raise SystemExit('spool refused: unexpected root owner or writable permissions')
owner_file = root / 'owner.json'

def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

def write(path, value):
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w') as out:
        json.dump(value, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)
    sync_dir(path.parent)

def owned(path):
    if owner_file.is_symlink() or not owner_file.is_file():
        raise SystemExit('spool refused: missing ownership record')
    owner = json.loads(owner_file.read_text())
    if (owner.get('uid') != uid or owner.get('repo') != str(repo.resolve())
            or not owner.get('cycle') or owner_file.stat().st_uid != uid
            or path.is_symlink() or not path.is_dir() or path.stat().st_uid != uid):
        raise SystemExit('spool refused: unexpected path or ownership record')
    return owner

def reap(name):
    path = root / name
    if path.exists() or path.is_symlink():
        owned(path)
        shutil.rmtree(path)
        sync_dir(root)

def manifest(path):
    result = []
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in sorted(dirs + files):
            entry = Path(parent) / name
            rel = entry.relative_to(path).as_posix()
            # Control writes change this directory while committing the handoff.
            if rel == '.handoff' or (rel.startswith('.handoff/') and rel != '.handoff/metadata.json'):
                continue
            info = entry.lstat()
            mode = info.st_mode
            row = {'path': rel, 'mode': mode, 'size': info.st_size,
                   'mtime_ns': info.st_mtime_ns}
            if stat.S_ISLNK(mode):
                row['type'] = 'symlink'
                row['link'] = os.readlink(entry)
            elif stat.S_ISREG(mode):
                row['type'] = 'file'
            elif stat.S_ISDIR(mode):
                row['type'] = 'directory'
            else:
                raise SystemExit('spool refused: unsupported payload file type')
            result.append(row)
    return sorted(result, key=lambda row: row['path'])

building, pending, finished = (root / n for n in ('building', 'pending', 'finished'))
if action == 'init':
    # A finished item has already completed push and checkout reconciliation.
    reap('finished')
    if pending.exists() or pending.is_symlink():
        owned(pending)
    else:
        reap('building')
        owner_file.unlink(missing_ok=True)
elif action == 'begin':
    if any(p.exists() or p.is_symlink() for p in (building, pending, finished)):
        raise SystemExit('spool occupied: refusing a second production run')
    write(owner_file, {'uid': uid, 'repo': str(repo.resolve()), 'cycle': args[0],
                       'pid': os.getppid()})
    building.mkdir(mode=0o700)
    (building / '.handoff').mkdir(mode=0o700)
    sync_dir(root)
elif action == 'handoff':
    owned(building)
    if building.stat().st_dev != root.stat().st_dev:
        raise SystemExit('handoff refused: run and spool devices differ; atomic rename required')
    if pending.exists() or pending.is_symlink():
        raise SystemExit('spool occupied: refusing to overwrite unpublished work')
    snapshot, cycle, started, probe_finished = args
    observed = json.loads((building / 'health/latest.json').read_text())['checked_at']
    if not isinstance(observed, str) or not observed:
        raise SystemExit('handoff refused: missing original observation time')
    meta = {'source_snapshot': snapshot, 'cycle': cycle, 'observed_at': observed,
            'cycle_started': int(started), 'probe_finished_at': probe_finished}
    write(building / '.handoff/metadata.json', meta)
    rows = manifest(building)
    write(building / '.handoff/manifest.json', rows)
    # os.rename refuses cross-device moves; unlike mv it can never copy gigabytes.
    os.rename(building, pending)
    sync_dir(root)
    write(pending / '.handoff/READY', meta)
elif action in ('resume', 'start-derivatives'):
    owner = owned(pending)
    meta = json.loads((pending / '.handoff/metadata.json').read_text())
    if meta['cycle'] != owner['cycle']:
        raise SystemExit('spool refused: cycle ownership mismatch')
    ready = pending / '.handoff/READY'
    started = pending / '.handoff/derivatives-started'
    if not started.exists() and (action == 'start-derivatives' or not ready.exists()):
        actual = manifest(pending)
        expected = json.loads((pending / '.handoff/manifest.json').read_text())
        # Timestamps are provenance, not a payload contract: a plain cp restore
        # changes mtime without changing what the publisher consumes. Compare
        # size, mode, type, relative path and link target, retaining mtime on disk.
        for row in actual + expected:
            row.pop('mtime_ns', None)
        if actual != expected:
            raise SystemExit('spool refused: handoff manifest mismatch')
    if not ready.exists():
        # Recover a kill between the directory rename and ready-marker rename.
        write(ready, meta)
    if json.loads(ready.read_text()) != meta:
        raise SystemExit('spool refused: ready metadata mismatch')
    if json.loads((pending / 'health/latest.json').read_text())['checked_at'] != meta['observed_at']:
        raise SystemExit('spool refused: original observation time changed')
    if action == 'start-derivatives': write(started, meta)
elif action == 'abandon':
    reap('building')
    if not pending.exists(): owner_file.unlink(missing_ok=True)
elif action == 'retire':
    owned(pending)
    os.rename(pending, finished)
    sync_dir(root)
    reap('finished')
    owner_file.unlink()
    sync_dir(root)
else:
    raise SystemExit('unknown spool operation: ' + action)
PY
  then
    return 0
  else
    rc=$?
  fi
  if [[ "$1" == handoff && ( "$rc" == 124 || "$rc" == 137 ) ]]; then
    log "handoff failed: timeout after ${SPOOL_HANDOFF_TIMEOUT_SECONDS}s (5s kill grace)"
  fi
  return "$rc"
}

publisher_hold() {
  log "publisher hold cycle=$cycle snapshot=$source_snapshot reason=$1; ready observation retained"
  telemetry publish.gate 0 skipped "{\"reason\":\"$1\",\"source_snapshot\":\"$source_snapshot\"}"
}

publisher_admission() {
  if publication_admission_guard; then return 0; fi
  if [[ "$publication_waiting" == true ]]; then
    publisher_hold publication_in_flight
  else
    publisher_hold publish_branch_fetch_failed
  fi
  return 1
}

record_spool_commit() {
  [[ -f "$run_dir/.handoff/READY" ]] || return 0
  git_repo rev-parse HEAD > "$run_dir/.handoff/artifact-commit.tmp"
  mv "$run_dir/.handoff/artifact-commit.tmp" "$run_dir/.handoff/artifact-commit"
  git_repo branch --show-current > "$run_dir/.handoff/artifact-branch"
  sync -f "$run_dir/.handoff/artifact-commit"
}

spool_commit_pushed() {
  local artifact
  if [[ -f "$run_dir/.handoff/READY" ]]; then
    artifact="$(<"$run_dir/.handoff/artifact-commit")"
  else
    # The shared transaction can also be exercised independently of a spool.
    artifact="$(git_repo rev-parse HEAD)"
  fi
  if [[ -f "$run_dir/.handoff/pushed-commit" \
      && "$(<"$run_dir/.handoff/pushed-commit")" == "$artifact" ]]; then
    return 0
  fi
  refresh_publish_branch || return 1
  if [[ -z "$fetched_publish_head" ]] \
      || ! git_repo merge-base --is-ancestor "$artifact" "$fetched_publish_head"; then
    return 1
  fi
  if [[ -f "$run_dir/.handoff/READY" ]]; then
    printf '%s\n' "$artifact" > "$run_dir/.handoff/pushed-commit"
    sync -f "$run_dir/.handoff/pushed-commit"
  fi
}

# A crash can leave the swap between its two renames. Persist its base and old
# targets before any swap; backup/new existence then proves which moves ran.
record_spool_transaction() {
  [[ -f "$run_dir/.handoff/READY" ]] || return 0
  "$PYTHON_BIN" - "$run_dir/.handoff/transaction.json" "$publish_root" \
    "$repo" "$(git_repo rev-parse HEAD)" "${ARTIFACT_PATHS[@]}" <<'PY'
import json, os, sys
from pathlib import Path
path, scratch, repo, base, *targets = sys.argv[1:]
record = {'scratch': scratch, 'base': base,
          'old': [t for t in targets if os.path.lexists(Path(repo) / t)]}
with open(path + '.tmp', 'w') as out:
    json.dump(record, out)
    out.flush()
    os.fsync(out.fileno())
os.replace(path + '.tmp', path)
fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
try: os.fsync(fd)
finally: os.close(fd)
PY
}

recover_spool_transaction() {
  local journal="$run_dir/.handoff/transaction.json" target base head candidate
  [[ -f "$journal" ]] || return 0
  recovering_publish=true
  candidate="$(jq -er .scratch "$journal")"
  base="$(jq -er .base "$journal")"
  [[ "$candidate" == "$repo/".datapulse-publish.* \
      && "$(canonical_path "$candidate")" == "$candidate" ]] \
    || die 'publish recovery refused: unexpected transaction scratch path or owner'
  if [[ ! -e "$candidate" && ! -L "$candidate" ]]; then
    # Allocation never started, or a previous cleanup finished its deletion.
    publish_root=""
    rm -- "$journal"
    recovering_publish=false
    return 0
  fi
  [[ -d "$candidate" && ! -L "$candidate" \
      && "$(stat -c %u "$candidate")" == "$(id -u)" ]] \
    || die 'publish recovery refused: unexpected transaction scratch owner'
  publish_root="$candidate"
  head="$(git_repo rev-parse HEAD)"
  if [[ -s "$run_dir/.handoff/artifact-commit" ]]; then
    log 'publisher retaining committed observation while cleaning transaction backup'
  elif [[ "$head" != "$base" ]]; then
    assert_managed_commits "$base"
    record_spool_commit
    log "publisher recovered committed transaction $head"
  elif [[ ! -s "$run_dir/.handoff/artifact-commit" ]]; then
    publish_swapped=true
    for target in "${ARTIFACT_PATHS[@]}"; do
      swapped_paths+=("$target")
      if [[ -e "$publish_root/backup/$target" || -L "$publish_root/backup/$target" ]]; then
        old_target_moved["$target"]=true
        new_target_moved["$target"]=true
      elif ! jq -e --arg t "$target" '.old | index($t)' "$journal" >/dev/null \
          && [[ ! -e "$publish_root/new/$target" ]]; then
        new_target_moved["$target"]=true
      fi
    done
    rollback_publish
    publish_swapped=false
    swapped_paths=(); old_target_moved=(); new_target_moved=()
    log 'publisher recovered interrupted artifact swap'
  fi
  rm -rf -- "$publish_root"
  publish_root=""
  rm -- "$journal"
  recovering_publish=false
}

run_pipeline() {
  local snapshot probe_finished_at health_tmp stage_started cycle_started

  trap cleanup EXIT
  trap 'exit 143' TERM
  spool_control init
  if [[ -e "$spool_root/pending" ]]; then
    log "producer spool occupied; retaining pending observation for publisher"
    return 0
  fi
  preflight --producer
  snapshot="$fetched_origin"
  telemetry_file="${DATAPULSE_TELEMETRY_FILE:-$repo/var/log/stages.jsonl}"
  cycle="$(date -u +'%Y-%m-%dT%H:%M')"
  cycle_started="$(milliseconds)"
  spool_control begin "$cycle"
  run_dir="$spool_root/building"
  run_dir_owned=true

  log "probe snapshot $snapshot"
  stage_started="$(milliseconds)"
  git_repo archive "$snapshot" | tar -x -C "$run_dir"
  seed_buffered_artifacts

  # Seed the run dir with the live rolling history (gitignored, so absent from
  # the archive) so history accumulates across cycles instead of resetting.
  if [[ -f "$repo/health/history.jsonl" ]]; then
    mkdir -p "$run_dir/health"
    cp -a "$repo/health/history.jsonl" "$run_dir/health/history.jsonl"
  fi
  telemetry snapshot "$(( $(milliseconds) - stage_started ))" success '{"source":"git archive"}'
  health_tmp="$(mktemp "$run_dir/health/.latest.XXXXXX.json")"
  (
    cd "$run_dir"
    stage_name=""
    # shellcheck disable=SC2317 # Invoked by the ERR trap below.
    stage_failed() {
      local rc=$?
      if [[ -n "$stage_name" ]]; then
        telemetry "$stage_name" "$(( $(milliseconds) - stage_started ))" fail
      fi
      exit "$rc"
    }
    trap stage_failed ERR
    # heartbeat-FAIL watchdog removed: self-blocking; replaced by external alert path
    stage_started="$(milliseconds)"
    stage_name=probe
    log "probe started at $(date -Iseconds)"
    bash scripts/check.sh --due > "$health_tmp"
    jq -e . "$health_tmp" >/dev/null
    mv "$health_tmp" health/latest.json
    # Resolve only from this cycle's confirmed observations, before the quality
    # profile or the producer's own surface generators can embed a stale URL.
    # Like its neighbours, failure aborts this subshell with probe telemetry.
    ${PYTHON_BIN} scripts/gen_dynamic_manifest_urls.py
    ${PYTHON_BIN} scripts/gen_quality_profile.py \
      --manifest datapulse.json \
      --health health/latest.json
    telemetry probe "$(( $(milliseconds) - stage_started ))" success
    stage_name=""
    stage_started="$(milliseconds)"
    stage_name=validate
    ${PYTHON_BIN} scripts/validate_at_runtime.py --input "$run_dir" --schemas "$run_dir"
    telemetry validate "$(( $(milliseconds) - stage_started ))" success
    stage_name=""
    stage_started="$(milliseconds)"
    stage_name=history
    ${PYTHON_BIN} scripts/gen_health_history.py --cycle "$cycle" --compact
    telemetry history "$(( $(milliseconds) - stage_started ))" success
    stage_name=""
    stage_started="$(milliseconds)"
    stage_name=evidence
    ${PYTHON_BIN} scripts/gen_trends.py
    ${PYTHON_BIN} scripts/gen_drift.py
    ${PYTHON_BIN} scripts/gen_reconciliation.py
    telemetry evidence "$(( $(milliseconds) - stage_started ))" success
    stage_name=""
  )
  probe_finished_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  spool_control handoff "$snapshot" "$cycle" "$cycle_started" "$probe_finished_at"
  run_dir_owned=false
  run_dir="$spool_root/pending"
  log "producer handed off cycle=$cycle snapshot=$snapshot observed_at=$(jq -r .observed_at "$run_dir/.handoff/READY")"
}

run_publisher() {
  local snapshot source_snapshot probe_finished_at probed stage_started cycle_started heartbeat health_tmp publish_output base_rc align_rc

  trap cleanup EXIT
  trap 'exit 143' TERM
  spool_control init
  if [[ ! -d "$spool_root/pending" ]]; then
    # Receipts committed after a previous artifact push still need transport,
    # even when no new observation is queued. Keep that recovery in this unit.
    preflight
    fetch_origin
    if [[ "$(git_repo rev-parse HEAD)" != "$fetched_origin" \
        && "$(publication_state_sha)" == "$(git_repo rev-parse HEAD)" ]]; then
      reconcile_after_publish
    fi
    log 'publisher idle; no ready observation'
    return 0
  fi
  spool_control resume
  run_dir="$spool_root/pending"
  telemetry_file="${DATAPULSE_TELEMETRY_FILE:-$repo/var/log/stages.jsonl}"
  snapshot="$(jq -er .source_snapshot "$run_dir/.handoff/READY")"
  source_snapshot="$snapshot"
  cycle="$(jq -er .cycle "$run_dir/.handoff/READY")"
  cycle_started="$(jq -er .cycle_started "$run_dir/.handoff/READY")"
  probe_finished_at="$(jq -er .probe_finished_at "$run_dir/.handoff/READY")"
  recover_spool_transaction
  preflight
  fetch_origin
  # A killed/failed transport may already have committed or pushed this item.
  # Reconcile that transaction before admitting or regenerating another one.
  if [[ -s "$run_dir/.handoff/artifact-commit" ]]; then
    # preflight may have replayed the pending commit on newly advanced main.
    # Accept its replacement only on the same cycle branch, behind the existing
    # managed-commit and main-ancestry fences.
    if [[ "$(git_repo branch --show-current)" == "$(<"$run_dir/.handoff/artifact-branch")" ]] \
        && ! git_repo merge-base --is-ancestor "$(<"$run_dir/.handoff/artifact-commit")" HEAD; then
      git_repo merge-base --is-ancestor "$fetched_origin" HEAD \
        || die 'publisher recovery refused: replacement commit is not forward of main'
      assert_managed_commits "$fetched_origin"
      record_spool_commit
    fi
    if ! spool_commit_pushed; then
      publisher_admission || return 0
      push_head --force
      record_spool_commit
      spool_commit_pushed || { publisher_hold transport_deferred; return 0; }
    fi
    log "publisher recovered pushed observation cycle=$cycle"
    publisher_post_publish
    return 0
  fi
  publisher_admission || return 0
  # Source provenance remains frozen, while the transaction base belongs to
  # this activation's checkout. Rewinding HEAD to yesterday's source snapshot
  # would turn already-promoted artifacts into dirt and deadlock reset --keep.
  if ! publish_base_current "$source_snapshot" "$fetched_origin" "$source_snapshot"; then
    apply_publish_deferral 'source snapshot is no longer reachable' \
      "publisher held: source snapshot $source_snapshot is on neither main nor the publish branch"
  fi
  snapshot="$(git_repo rev-parse HEAD)"
  spool_control start-derivatives
  (
    cd "$run_dir"
    stage_name=""
    # shellcheck disable=SC2317 # Invoked by the ERR trap below.
    stage_failed() {
      local rc=$?
      if [[ -n "$stage_name" ]]; then
        telemetry "$stage_name" "$(( $(milliseconds) - derivative_started ))" fail
      fi
      exit "$rc"
    }
    trap stage_failed ERR
    derivative_started="$(milliseconds)"
    # Stable per-generator suffixes: gen_badges, gen_rss, gen_readme_summary,
    # gen_catalog_snapshot, gen_record_evidence, gen_evidence_coverage,
    # gen_catalog_graph, and gen_public_summary.
    stage_name=deltas
    command_started="$(milliseconds)"
    bash scripts/gen_badges.sh
    telemetry deltas.gen_badges "$(( $(milliseconds) - command_started ))" success
    command_started="$(milliseconds)"
    bash scripts/gen_rss.sh
    telemetry deltas.gen_rss "$(( $(milliseconds) - command_started ))" success
    command_started="$(milliseconds)"
    bash scripts/gen_readme_summary.sh
    telemetry deltas.gen_readme_summary "$(( $(milliseconds) - command_started ))" success
    command_started="$(milliseconds)"
    ${PYTHON_BIN} scripts/gen_catalog_snapshot.py
    telemetry deltas.gen_catalog_snapshot "$(( $(milliseconds) - command_started ))" success
    command_started="$(milliseconds)"
    ${PYTHON_BIN} scripts/gen_record_evidence.py
    telemetry deltas.gen_record_evidence "$(( $(milliseconds) - command_started ))" success
    command_started="$(milliseconds)"
    ${PYTHON_BIN} scripts/gen_evidence_coverage.py
    telemetry deltas.gen_evidence_coverage "$(( $(milliseconds) - command_started ))" success
    command_started="$(milliseconds)"
    ${PYTHON_BIN} scripts/gen_catalog_graph.py
    telemetry deltas.gen_catalog_graph "$(( $(milliseconds) - command_started ))" success
    # Public rollup of the snapshot written in the probe stage. It is a served surface
    # published from git, so it is generated here and committed with health/latest.json
    # in the same cycle instead of going stale silently.
    command_started="$(milliseconds)"
    ${PYTHON_BIN} scripts/gen_public_summary.py
    telemetry deltas.gen_public_summary "$(( $(milliseconds) - command_started ))" success
    telemetry deltas "$(( $(milliseconds) - derivative_started ))" success
    stage_name=""
    derivative_started="$(milliseconds)"
    stage_name=passports
    ${PYTHON_BIN} scripts/gen_dataset_passports.py
    telemetry passports "$(( $(milliseconds) - derivative_started ))" success
    stage_name=""
    derivative_started="$(milliseconds)"
    stage_name=deltas.gen_dataset_pages
    ${PYTHON_BIN} scripts/gen_dataset_pages.py
    telemetry deltas.gen_dataset_pages "$(( $(milliseconds) - derivative_started ))" success
    stage_name=""
    # The OKF bundle is a projection of the snapshot this run just rendered, so
    # refresh it before validation and staging; the existing publish path then
    # commits docs/okf with the health data it projects. run_okf_refresh is
    # self-gating (daily) and deliberately non-fatal, so it can never fail this
    # probe subshell.
    run_okf_refresh
    derivative_started="$(milliseconds)"
    stage_name=kv-index
    # KV is a dashboard acceleration only. Preserve its explicit result in the
    # service log, but never let an auxiliary write block health publication.
    if publish_output="$(${PYTHON_BIN} scripts/publish_health_index.py 2>&1)"; then
      publisher_rc=0
      log "$publish_output"
    else
      publisher_rc=$?
      log "health index publisher exited non-zero: $publish_output"
    fi
    if (( publisher_rc == 0 )); then
      telemetry kv-index "$(( $(milliseconds) - derivative_started ))" success
    elif (( publisher_rc == 3 )); then
      telemetry kv-index "$(( $(milliseconds) - derivative_started ))" skipped '{"reason":"cadence_window"}'
    else
      # The publisher's terse failure line is useful telemetry, but never
      # allow a token-shaped value from an upstream exception into state.
      kv_error_json="$(
        ${PYTHON_BIN} - "$publish_output" <<'PY'
import json
import re
import sys

reason = (sys.argv[1].splitlines() or [""])[0][:200]
reason = re.sub(r'(?i)(\b(?:api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*)(?:Bearer\s+)?\S+', r'\1<redacted>', reason)
reason = re.sub(r'(?i)([?&](?:api[_-]?key|token|secret|password)\=)[^&\s]+', r'\1<redacted>', reason)
reason = re.sub(r'(?<=://)[^/@\s:]+(?::[^/@\s]*)?@', '<redacted>@', reason)
print(json.dumps({"error": reason}, ensure_ascii=True, separators=(",", ":")))
PY
      )"
      telemetry kv-index "$(( $(milliseconds) - derivative_started ))" fail "$kv_error_json"
    fi
    stage_name=""
  )
  probed="$(jq -r '.datasets | length' "$run_dir/health/latest.json")"
  log "probe finished at $(date -Iseconds); $probed datasets probed"
  validate_staged_output
  # observation-receipts/ is a managed artifact, so stage_artifacts() below needs
  # the path to exist. Seed it from the live checkout now; the signer then runs
  # after the artifact commit and appends to this same chain. Signing here would
  # be too early to name the commit that carries the artifact.
  prepare_observation_receipts "$(milliseconds)"
  heartbeat="$(git_repo show "$snapshot:health/latest.json" | jq -r '._trust_summary.pipeline_heartbeat_at // empty')"
  if [[ -n "$heartbeat" ]]; then
    jq --arg heartbeat "$heartbeat" '._trust_summary.pipeline_heartbeat_at = $heartbeat' "$run_dir/health/latest.json" > "$run_dir/health/.latest-with-heartbeat.json"
    mv "$run_dir/health/.latest-with-heartbeat.json" "$run_dir/health/latest.json"
  fi

  # Publication is permitted only if the frozen source commit is still local
  # HEAD and is contained by origin/main or already published on the automation
  # branch. A refused base is retried once through reconcile, which re-bases the
  # cycle onto the newest origin/main; a race after this check is caught by the
  # final fetch-and-push and leaves a verified pending artifact commit.
  # Per-sub-step publish timings. The two `telemetry publish` rows below keep
  # carrying the cycle lag (elapsed since cycle_started); these rows carry each
  # step's own cost so a receipt can attribute the publish path instead of
  # reading the whole cycle as "publishing".
  stage_started="$(milliseconds)"
  fetch_origin
  publication_admission_guard || {
    if [[ "$publication_waiting" == true ]]; then
      publisher_hold publication_in_flight
      telemetry publish.gate "$(( $(milliseconds) - stage_started ))" skipped \
        '{"reason":"publication_in_flight"}'
    else
      publisher_hold publish_branch_fetch_failed
      telemetry publish.gate "$(( $(milliseconds) - stage_started ))" skipped \
        '{"reason":"publish_branch_fetch_failed"}'
    fi
    run_observation_signing
    run_mcp_sync || return $?
    run_observation_capture
    exit 0
  }
  case "$publication_buffered" in
    true)
    # A squash merge can leave a local receipt commit above the old base.
    # Keep its working-tree bytes while moving HEAD to the fetched main.
    git_repo diff --cached --quiet \
      || die "publication resume refused: unrelated staged changes"
    if [[ "$(git_repo rev-parse HEAD)" != "$snapshot" ]]; then
      if ! git_repo merge-base --is-ancestor HEAD "$snapshot"; then
        git_repo merge-base HEAD "$snapshot" >/dev/null \
          || die "publication resume refused: no common base"
        assert_managed_commits "$(git_repo merge-base HEAD "$snapshot")"
      fi
      git_repo_index_retry reset --mixed "$snapshot"
    fi
    ;;
  esac
  base_rc=0
  publish_base_gate "$snapshot" || base_rc=$?
  case "$base_rc" in
    0) snapshot="$(git_repo rev-parse HEAD)" ;;
    1) apply_publish_deferral "origin/main no longer contains the probe base" \
         "publish skipped this cycle: origin/main no longer contains the probe base ($snapshot -> $fetched_origin)" ;;
    2) apply_publish_deferral "local HEAD moved during probe" \
         "publish skipped this cycle: local HEAD moved during probe ($snapshot -> $(git_repo rev-parse HEAD))" ;;
    *) apply_publish_deferral "publish base check failed" \
         "publish skipped this cycle: publish base check failed ($snapshot -> $fetched_origin)" ;;
  esac
  case "$publication_buffered" in
    true) ;;
    *) assert_artifacts_clean ;;
  esac
  # Establish the forward-base invariant at the point of commit, before the
  # commit exists: a checkout still parked on an already-published publish is
  # re-based onto the newest origin/main here, so the branch tip this cycle
  # pushes is always a descendant of main. A refusal to move -- a local commit
  # the publish branch does not carry, or a working tree that overlaps the
  # reset -- defers the cycle rather than publishing from a stale base.
  align_rc=0
  align_publish_base || align_rc=$?
  case "$align_rc" in
    0) snapshot="$(git_repo rev-parse HEAD)" ;;
    1) apply_publish_deferral "local HEAD is not on origin/$PUBLISH_BRANCH" \
         "publish skipped this cycle: local HEAD is not on origin/$PUBLISH_BRANCH and cannot be re-based onto origin/main" ;;
    *) apply_publish_deferral "publish could not re-base onto origin/main" \
         "publish skipped this cycle: could not re-base onto origin/main ($(git_repo rev-parse HEAD) -> $fetched_origin)" ;;
  esac
  telemetry publish.gate "$(( $(milliseconds) - stage_started ))" success

  begin_publish_checkout
  log "publish staging validated artifacts into live checkout"
  stage_started="$(milliseconds)"
  stage_artifacts
  telemetry publish.stage-artifacts "$(( $(milliseconds) - stage_started ))" success

  # The changes branch performs one more swap (the attested score) after the
  # shared `git add -A`, so publish.swap is emitted inside each branch once the
  # last swap for that branch has run.
  stage_started="$(milliseconds)"
  swap_artifacts
  git_repo_index_retry add -A -- "${ARTIFACT_PATHS[@]}"

  if git_repo diff --cached --quiet -- "${ARTIFACT_PATHS[@]}"; then
    telemetry publish.swap "$(( $(milliseconds) - stage_started ))" success
    stage_started="$(milliseconds)"
    heartbeat="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    health_tmp="$(mktemp "$repo/health/.heartbeat.XXXXXX.json")"
    jq --arg heartbeat "$heartbeat" \
      '._trust_summary.pipeline_heartbeat_at = $heartbeat' \
      "$repo/health/latest.json" > "$health_tmp" \
      && mv "$health_tmp" "$repo/health/latest.json"
    git_repo_index_retry add -- health/latest.json
    telemetry publish.add "$(( $(milliseconds) - stage_started ))" success
    stage_started="$(milliseconds)"
    git_repo update-ref "$PENDING_BASE_REF" "$snapshot"
    pending_ref_created=true
    git_repo_index_retry -c user.name="Redza Halim" -c user.email="r3dz4r@gmail.com" \
      commit -m "$HEARTBEAT_COMMIT_PREFIX $heartbeat" -- health/latest.json
    telemetry publish.commit "$(( $(milliseconds) - stage_started ))" success
    publish_swapped=false
    record_spool_commit
    stage_started="$(milliseconds)"
    if [[ "$publication_buffered" == true ]]; then
      push_head --force
    else
      push_head
    fi
    record_spool_commit
    spool_commit_pushed || { publisher_hold transport_deferred; return 0; }
    telemetry publish.push "$(( $(milliseconds) - stage_started ))" success
    telemetry publish "$(( $(milliseconds) - cycle_started ))" success "{\"lag_ms\":$(( $(milliseconds) - cycle_started )),\"publication_lag_ms\":$(( $(milliseconds) - cycle_started ))}"
    log "publish pushed heartbeat"
  else
    log "publish committing changed artifacts"
    telemetry publish.swap "$(( $(milliseconds) - stage_started ))" success
    stage_started="$(milliseconds)"
    heartbeat="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    health_tmp="$(mktemp "$repo/health/.heartbeat.XXXXXX.json")"
    jq --arg heartbeat "$heartbeat" \
      '._trust_summary.pipeline_heartbeat_at = $heartbeat' \
      "$repo/health/latest.json" > "$health_tmp" \
      && mv "$health_tmp" "$repo/health/latest.json"
    git_repo_index_retry add -- health/latest.json
    telemetry publish.add "$(( $(milliseconds) - stage_started ))" success
    stage_started="$(milliseconds)"
    git_repo update-ref "$PENDING_BASE_REF" "$snapshot"
    pending_ref_created=true
    git_repo_index_retry -c user.name="Redza Halim" -c user.email="r3dz4r@gmail.com" \
      commit -m "$COMMIT_MESSAGE" -- "${MANAGED_ARTIFACT_PATHS[@]}"
    telemetry publish.commit "$(( $(milliseconds) - stage_started ))" success
    publish_swapped=false
    record_spool_commit
    stage_started="$(milliseconds)"
    if [[ "$publication_buffered" == true ]]; then
      push_head --force
    else
      push_head
    fi
    record_spool_commit
    spool_commit_pushed || { publisher_hold transport_deferred; return 0; }
    telemetry publish.push "$(( $(milliseconds) - stage_started ))" success
    telemetry publish "$(( $(milliseconds) - cycle_started ))" success "{\"lag_ms\":$(( $(milliseconds) - cycle_started )),\"publication_lag_ms\":$(( $(milliseconds) - cycle_started ))}"
    log "publish pushed chore(health)"
  fi

  publisher_post_publish
}

restore_live_checkout() {
  local status="$1" ref="$2" commit="$3" current_ref
  current_ref="$(git_repo symbolic-ref --short -q HEAD || git_repo rev-parse HEAD)"
  if [[ "$current_ref" != "$ref" || "$(git_repo rev-parse HEAD)" != "$commit" ]]; then
    git_repo checkout -q "$ref" || return $?
    log "publisher restored checkout $ref"
  fi
  return "$status"
}

publisher_post_publish() {
  local artifact checkout_ref checkout_commit checkout_traps checkout_exit_action
  artifact="$(<"$run_dir/.handoff/artifact-commit")"
  if ! git_repo merge-base --is-ancestor "$artifact" HEAD; then
    # preflight leaves HEAD behind origin/main while a publication is in
    # flight, so a checkout that origin/main has since advanced past has not
    # moved; reconcile_after_publish fast-forwards it after these stages.
    git_repo merge-base --is-ancestor HEAD "$fetched_origin" \
      || die 'publisher post-push recovery refused: checkout moved unexpectedly'
    assert_artifacts_clean
    checkout_ref="$(git_repo symbolic-ref --short -q HEAD || git_repo rev-parse HEAD)"
    checkout_commit="$(git_repo rev-parse HEAD)"
    checkout_traps="$(trap -p EXIT RETURN HUP INT TERM)"
    checkout_exit_action="$(trap -p EXIT)"
    # Decode Bash's own quoted trap declaration so the original cleanup still
    # sees the failing stage's status, after the checkout has been restored.
    checkout_exit_action="${checkout_exit_action#trap -- }"
    checkout_exit_action="${checkout_exit_action% EXIT}"
    eval "checkout_exit_action=${checkout_exit_action:-\"''\"}"
    # Errexit unwinds function locals before EXIT, so freeze the refs and the
    # previous handler into the trap rather than looking them up at exit time.
    printf -v checkout_exit_action 'if restore_live_checkout "$?" %q %q; then\n%s\nelse\n%s\nfi' \
      "$checkout_ref" "$checkout_commit" "${checkout_exit_action:-:}" "${checkout_exit_action:-:}"
    # shellcheck disable=SC2064 # Freeze locals before errexit unwinds them.
    trap "$checkout_exit_action" EXIT
    # RETURN covers normal completion and early returns without leaking these
    # traps into the rest of the publisher. EXIT also covers die and errexit.
    trap 'restore_live_checkout 0 "$checkout_ref" "$checkout_commit" \
      || die "publisher checkout restore failed"
      trap - EXIT RETURN HUP INT TERM
      eval "$checkout_traps"' RETURN
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
    git_repo checkout -q --detach "$artifact"
  fi
  # Evidence only: no reader or publication gate consults this ref.
  if ! run_shadow_snapshot "$source_snapshot" "$probe_finished_at"; then
    log 'warning: snapshot.shadow telemetry failed; continuing health cycle'
  fi

  # Publication succeeded, so the deferral stall is over and the counter starts
  # fresh. Like the increment path, a reset that cannot write logs and continues.
  clear_publish_deferral_state

  # Sign the artifact of the newest already-published commit, not the commit
  # push_head just made. The signer's mirror materializes only the source
  # repository's main and the health-automation merge has not run yet, so the
  # fresh commit is refused; run_observation_signing resolves the published ref
  # itself and the receipt attests those bytes. It remains fail-soft: it can
  # never turn an evidence problem into a health outage. It runs before the
  # post-publish stages so the top-level stage order (and the capture test that
  # pins it) is unchanged.
  run_observation_signing

  run_mcp_sync
  run_observation_capture
  run_shadow_health_publication
  run_pipeline_receipt

  # Publish succeeded, and every post-publish stage has finished binding to
  # HEAD and the live artifact tree; only now is it safe to return the checkout
  # to agreement with origin/main. Reconciling earlier in the flow would reset
  # health/latest.json out from under observation signing's staged-vs-live
  # digest check and shadow health's comparison.
  reconcile_after_publish
  if [[ -n "$publish_root" ]]; then
    rm -rf -- "$publish_root"
    publish_root=""
    rm -f -- "$run_dir/.handoff/transaction.json"
  fi
  spool_control retire
  run_dir=""
  log "publisher completed remote push cycle=$cycle; merge and served publication are separate"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  # Keep the sandbox interlock on every mode, including the read-only probe.
  assert_publish_target_safe

  case "${1:-}" in
    --run|--produce|--publish|--preflight|--push-only)
      # Sandboxes must never open the installed observer's lock file.
      health_lock="$repo/.git/datapulse-health.lock"
      [[ "$(canonical_path "$repo")" != "$(canonical_path "$DEFAULT_REPO")" ]] \
        || health_lock=/tmp/datapulse-health.lock
      exec 9>"${DATAPULSE_HEALTH_LOCK:-$health_lock}"
      if ! flock -n 9; then
        if [[ "${1:-}" == --produce ]]; then
          run_dir="$repo"
          telemetry_file="${DATAPULSE_TELEMETRY_FILE:-$repo/var/log/stages.jsonl}"
          cycle="$(date -u +'%Y-%m-%dT%H:%M')"
          telemetry lock 0 skipped '{"reason":"lock_busy"}'
        fi
        log 'health lock busy; leaving work for the next activation'
        exit 0
      fi
      ;;
  esac
  case "${1:-}" in
    check-hold)
      check_publication_hold
      ;;
    --preflight)
      preflight
      ;;
    --push-only)
      push_head --force
      if [[ "$publication_waiting" != true ]]; then
        reconcile_after_publish
      fi
      ;;
    --run|--produce)
      run_pipeline
      ;;
    --publish)
      run_publisher
      ;;
    *)
      printf 'Usage: %s check-hold|--preflight|--push-only|--produce|--publish|--run\n' "$0" >&2
      exit 2
      ;;
  esac
fi
