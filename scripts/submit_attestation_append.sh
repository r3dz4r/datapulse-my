#!/usr/bin/env bash
# Submit a reviewed append candidate; publication waits for authoritative acceptance.
set -Eeuo pipefail
expected_source="$(git rev-parse HEAD)"
python3 scripts/verify_attestation_append.py --base "$expected_source"
if ! jq -e '.claims.rekor_witnessed == true' attestations/latest/binding.json >/dev/null; then
  if [[ "${DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION:-}" != "1" ]]; then
    echo 'Refusing append submission: its binding declares rekor_witnessed: false; a Rekor witness is required. Only an explicit DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION=1 permits unwitnessed publication.' >&2
    exit 1
  fi
fi
git fetch origin main
git merge-base --is-ancestor "$expected_source" origin/main || {
  echo 'Discarding candidate: its source is not in origin/main history.' >&2
  exit 1
}
head="$(jq -er '.current_head' attestations/chain-index.json)"
day="$(jq -er '.date' attestations/latest/index.json)"
branch="attestation/append-$head"
git config user.name github-actions[bot]
git config user.email 41898282+github-actions[bot]@users.noreply.github.com
git switch -c "$branch"
# Stage only immutable evidence and the discovery index here. Every mutable
# projection promote() rewrites (latest/ and the legacy mirror) is staged after
# the refresh below, so no pre-refresh mirror can enter the commit.
git add -- "attestations/$day" attestations/chain-index.json
if [[ -d "attestations/rekor/$day" ]]; then
  git add -- "attestations/rekor/$day"
fi
git diff --cached --quiet && exit 0
message="$(git diff --cached --name-only | python3 scripts/attestation_commit_back.py --date "$day")"
[[ -n "$message" ]]
git commit -m "$message"
if [[ "$(git rev-parse origin/main)" != "$expected_source" ]]; then
  git merge --no-edit origin/main || {
    echo 'Discarding candidate: merging origin/main failed; manual reconciliation required.' >&2
    exit 1
  }
fi
# Resolve the directory selected by the chain index only after aligning to the
# accepted base. That index is authoritative for the current head; a pre-merge
# directory selection can leave the legacy mirror behind the accepted head.
resolve_day_directory_after_alignment() {
  local head_path
  head_path="$(jq -er '.heads[.current_head]' attestations/chain-index.json)"
  dirname "$head_path"
}
day_directory="$(resolve_day_directory_after_alignment)"
# Reuse promote() for projection construction and leave dated evidence untouched.
refresh_projection_from_accepted_base() {
  python3 - "$1" <<'PY'
import sys
from pathlib import Path

from scripts.gen_attestations import promote

promote(Path.cwd(), sys.argv[1])
PY
}
refresh_projection_from_accepted_base "$day_directory"
# promote() rewrites these mutable projections, including the legacy chain-head
# mirror. Stage them only after the refresh: an add before it snapshots the
# pre-refresh mirror that acceptance then rejects.
git add -- attestations/latest/chain_head.json attestations/latest/index.json \
  attestations/latest/binding.json attestations/latest/scores.json \
  .attestations/chain_head.json
git commit --amend --no-edit
# Credentials stay in the runner environment; neither configuration nor logs
# contain their values. A unique hash branch is never force-updated or rebased.
git -c 'credential.helper=!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f' \
  push origin "HEAD:refs/heads/$branch"
gh pr create --base main --head "$branch" \
  --title "chore(attestations): append signed set $day" \
  --body "Append immutable signed evidence from source $expected_source. Publication must wait for this append to be accepted; existing evidence is preserved."
