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
git add -- "attestations/$day" attestations/latest/index.json \
  attestations/latest/binding.json attestations/latest/chain_head.json \
  attestations/chain-index.json .attestations/chain_head.json
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
# The projection was built against the checkout as it stood when the job began;
# after merging the freshly-fetched accepted base it can hold a mixture of the
# append's day and that base. Re-derive it on the aligned tree so acceptance
# never compares the append against a projection from an older checkout. The
# repository's generator owns projection construction: reuse promote() instead
# of copying or rewriting pointers here, and leave dated evidence untouched.
refresh_projection_from_accepted_base() {
  local directory
  directory="$(dirname "$(jq -er --arg head "$head" '.heads[$head]' attestations/chain-index.json)")"
  python3 - "$directory" <<'PY'
import sys
from pathlib import Path

from scripts.gen_attestations import promote

promote(Path.cwd(), sys.argv[1])
PY
  git add -- attestations/latest/chain_head.json attestations/latest/index.json \
    attestations/latest/binding.json attestations/latest/scores.json \
    .attestations/chain_head.json
  git commit --amend --no-edit
}
refresh_projection_from_accepted_base
# Credentials stay in the runner environment; neither configuration nor logs
# contain their values. A unique hash branch is never force-updated or rebased.
git -c 'credential.helper=!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f' \
  push origin "HEAD:refs/heads/$branch"
gh pr create --base main --head "$branch" \
  --title "chore(attestations): append signed set $day" \
  --body "Append immutable signed evidence from source $expected_source. Publication must wait for this append to be accepted; existing evidence is preserved."
