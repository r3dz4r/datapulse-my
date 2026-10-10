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
# Identity and discovery come from verified signed content, never a date alias.
readarray -t identity < <(python3 - <<'IDENTITY'
from pathlib import Path
from scripts.attestation_sets import discovery
value = discovery(Path.cwd())
head = value["current_head"]
print(head)
print(value["envelopes"][head]["date"])
IDENTITY
)
head="${identity[0]}"
day="${identity[1]}"
branch="attestation/append-$head"
# Check the freshly fetched accepted parent without rewriting a signed candidate.
python3 scripts/verify_attestation_append.py --base origin/main
path_output="$(python3 scripts/verify_attestation_append.py --base origin/main --print-paths)"
[[ -n "$path_output" ]] || exit 0
readarray -t paths <<<"$path_output"
(( ${#paths[@]} )) || exit 0
git config user.name github-actions[bot]
git config user.email 41898282+github-actions[bot]@users.noreply.github.com
git switch -c "$branch"
# Only this finalized append's evidence enters Git. Discovery and publication
# projections are derived after acceptance, so concurrent commits share no writes.
git add -- "${paths[@]}"
git diff --cached --quiet && exit 0
message="$(git diff --cached --name-only | python3 scripts/attestation_commit_back.py --date "$day")"
[[ -n "$message" ]]
git commit -m "$message"
# Credentials stay in the runner environment; neither configuration nor logs
# contain their values. A unique hash branch is never force-updated or rebased.
git -c 'credential.helper=!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f' \
  push origin "HEAD:refs/heads/$branch"
gh pr create --base main --head "$branch" \
  --title "chore(attestations): append signed set $day" \
  --body "Append immutable signed evidence from source $expected_source. Publication must wait for this append to be accepted; existing evidence is preserved."
