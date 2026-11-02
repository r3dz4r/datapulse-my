#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf -- "$fixture"' EXIT
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
export GIT_ALLOW_PROTOCOL=file
export DATAPULSE_FETCH_ATTEMPTS=1 DATAPULSE_FETCH_RETRY_BASE_SECONDS=0
source "${PIPELINE_SCRIPT:-$root/scripts/datapulse-pipeline.sh}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

seed() {
  local name="$1"
  origin="$fixture/$name.git"
  repo="$fixture/$name"
  git init -q --bare --initial-branch=main "$origin"
  git init -q --initial-branch=main "$repo"
  git_repo config user.name 'Checkout test'
  git_repo config user.email checkout@example.invalid
  git_repo remote add origin "$origin"
  mkdir -p "$repo/health" "$repo/observation-receipts"
  printf 'initial\n' > "$repo/health/latest.json"
  printf 'operator file\n' > "$repo/operator.txt"
  git_repo add .
  git_repo commit -qm initial
  git_repo push -q -u origin main
  fetched_origin="$(git_repo rev-parse HEAD)"
  publish_recovery_attempted=false
}

# Exercise post-publish checkout handling with real Git refs, but keep signing,
# MCP and capture inside the fixture instead of contacting their live services.
post_publish_case() {
  local scenario="$1" expected_rc="$2" rc=0 artifact checkout_count
  seed "post-$scenario"
  git_repo checkout -qb artifact
  printf 'published artifact\n' > "$repo/health/latest.json"
  git_repo commit -qam "$COMMIT_MESSAGE"
  artifact="$(git_repo rev-parse HEAD)"
  git_repo checkout -q main
  [[ "$scenario" != ancestor ]] || artifact="$fetched_origin"
  mkdir -p "$fixture/post-run/.handoff"
  printf '%s\n' "$artifact" > "$fixture/post-run/.handoff/artifact-commit"
  bash -c '
    source "$1"
    repo="$2"; run_dir="$3"; fetched_origin="$4"; scenario="$5"
    source_snapshot="$4"; probe_finished_at=fixture; cycle=fixture
    trap '\''printf "cleanup:%s\n" "$?"'\'' EXIT
    trap '\''exit 143'\'' TERM
    original_traps="$(trap -p EXIT RETURN HUP INT TERM)"
    git_repo() {
      if [[ "$1" == checkout ]]; then printf "checkout\n" >> "$repo/checkouts.log"; fi
      git -C "$repo" "$@"
    }
    stage() {
      [[ "$(git_repo rev-parse HEAD)" == "$(<"$run_dir/.handoff/artifact-commit")" ]] \
        || die "stage ran on the wrong commit"
      printf "stage:%s\n" "$1"
    }
    run_shadow_snapshot() { stage snapshot; }
    clear_publish_deferral_state() { stage deferral; }
    run_observation_signing() { stage signing; }
    run_mcp_sync() {
      stage mcp
      case "$scenario" in
        die) die "injected stage failure" ;;
        errexit) return 71 ;;
        exit) exit 72 ;;
        TERM|INT|HUP) kill -s "$scenario" "$BASHPID" ;;
      esac
    }
    run_observation_capture() { stage capture; }
    run_shadow_health_publication() { stage shadow; }
    run_pipeline_receipt() { stage receipt; }
    reconcile_after_publish() { stage reconcile; }
    spool_control() { printf "spool:%s\n" "$1"; }
    publisher_post_publish
    [[ -z "$run_dir" ]] || die "post-publish state did not reach caller"
    [[ "$(trap -p EXIT RETURN HUP INT TERM)" == "$original_traps" ]] \
      || die "post-publish leaked traps"
    printf "returned:%s\n" "$(git_repo symbolic-ref --short -q HEAD || git_repo rev-parse HEAD)"
  ' bash "${PIPELINE_SCRIPT:-$root/scripts/datapulse-pipeline.sh}" "$repo" \
    "$fixture/post-run" "$fetched_origin" "$scenario" > "$fixture/output" 2>&1 || rc=$?
  if (( rc != expected_rc )); then
    cat "$fixture/output" >&2
    fail "$scenario returned $rc instead of $expected_rc"
  fi
  [[ "$(git_repo symbolic-ref --short -q HEAD)" == main ]] \
    || { cat "$fixture/output" >&2; fail "$scenario left checkout detached or on wrong branch"; }
  [[ "$(git_repo rev-parse HEAD)" == "$fetched_origin" ]] || fail "$scenario restored wrong commit"
  grep -Fxq "cleanup:$expected_rc" "$fixture/output" || fail "$scenario lost EXIT cleanup or status"
  if (( expected_rc == 0 )); then
    grep -Fxq 'returned:main' "$fixture/output" || fail "$scenario did not restore before return"
    [[ "$(sed -n 's/^stage://p' "$fixture/output" | paste -sd ,)" == \
      snapshot,deferral,signing,mcp,capture,shadow,receipt,reconcile ]] || fail "$scenario changed stage order"
  fi
  checkout_count=0
  [[ ! -f "$repo/checkouts.log" ]] || checkout_count="$(wc -l < "$repo/checkouts.log")"
  if [[ "$scenario" == ancestor ]]; then
    [[ "$checkout_count" == 0 ]] || fail 'ancestor path performed a checkout'
    if grep -Fq 'publisher restored checkout' "$fixture/output"; then fail 'ancestor logged a needless restore'; fi
    printf 'PASS: post-publish ancestor skips detach and restore\n'
  else
    [[ "$checkout_count" == 2 ]] || fail "$scenario did not detach and restore exactly once"
    [[ "$(grep -Fxc 'datapulse-health: publisher restored checkout main' "$fixture/output")" == 1 ]] \
      || fail "$scenario did not log exactly one restore"
    printf 'PASS: post-publish %s restores checkout and preserves exit status\n' "$scenario"
  fi
}

post_publish_case success 0
post_publish_case die 1
post_publish_case TERM 143
post_publish_case ancestor 0
