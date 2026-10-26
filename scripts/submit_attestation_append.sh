#!/usr/bin/env bash
# Submit a reviewed append candidate; publication waits for authoritative acceptance.
set -Eeuo pipefail
script="$(realpath "$0")"
old_pr="${2:-}"
old_branch="${3:-}"
old_sha="${4:-}"
if [[ "${1:-}" == --rebuild ]]; then
  [[ "$#" == 4 && "$old_pr" =~ ^[1-9][0-9]*$ && "$old_branch" == attestation/append-* && "$old_sha" =~ ^[0-9a-f]{40}$ ]]
  [[ ! "$old_branch" =~ -[0-9a-f]{12}$ ]] || {
    echo "Refusing a second append rebuild for $old_branch ($old_sha)." >&2
    exit 1
  }
elif (( $# != 0 )); then
  echo 'Usage: submit_attestation_append.sh [--rebuild PR_NUMBER BRANCH HEAD_SHA]' >&2
  exit 2
fi

write_noop_result() {
  if [[ -n "${APPEND_SUBMISSION_RESULT:-}" ]]; then
    printf 'noop - 0\n' > "$APPEND_SUBMISSION_RESULT"
  fi
}

write_successor_record() {
  local parent="$1" child="$2" path temporary
  [[ "$parent" =~ ^[0-9a-f]{64}$ && "$child" =~ ^[0-9a-f]{64}$ ]] || {
    echo 'Refusing successor record with an invalid parent or child head.' >&2
    return 1
  }
  path="attestations/successors/$parent.json"
  mkdir -p -- attestations/successors
  temporary="$(mktemp "${path}.tmp.XXXXXXXX")"
  printf '{"parent":"%s","child":"%s"}\n' "$parent" "$child" > "$temporary"
  mv -- "$temporary" "$path"
  printf '%s\n' "$path"
}

rebuild_from_main() {
  local old_parent="$1" new_base="$2" old_parent_head="$3" new_parent_head="$4"
  local binding="$5" reference published_at path current_pr witnessed_digest accepted_digest
  local -a old_paths=("${@:6}") witness_paths=() generation
  published_at="$(jq -er '.payload.published_at' <<<"$binding")"
  reference="$(jq -r '.rekor.reference_ref // empty' <<<"$binding")"
  rebuild_dir="$(mktemp -d "$PWD/.append-rebuild.XXXXXXXX")"
  worktree_added=0
  cleanup_rebuild() {
    local status=$?
    trap - EXIT
    if (( worktree_added )); then
      git worktree remove --force "$rebuild_dir" || exit 1
    else
      rmdir "$rebuild_dir" || exit 1
    fi
    exit "$status"
  }
  trap cleanup_rebuild EXIT
  git worktree add --detach "$rebuild_dir" "$new_base"
  worktree_added=1

  if [[ "$old_parent_head" == "$new_parent_head" ]]; then
    if [[ -z "$old_pr" ]]; then
      cp -a --parents -- "${old_paths[@]}" "$rebuild_dir"
    else
      git -C "$rebuild_dir" restore --source="$old_sha" --worktree -- "${old_paths[@]}"
    fi
  else
    [[ -s "${DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE:-}" ]] || {
      echo "Refusing append rebuild: accepted head $new_parent_head at $new_base replaced $old_parent_head at $old_parent; signing key unavailable." >&2
      exit 1
    }
    for path in "${old_paths[@]}"; do
      [[ "$path" == attestations/rekor/* ]] && witness_paths+=("$path")
    done
    if (( ${#witness_paths[@]} )); then
      if [[ -z "$old_pr" ]]; then
        cp -a --parents -- "${witness_paths[@]}" "$rebuild_dir"
      else
        git -C "$rebuild_dir" restore --source="$old_sha" --worktree -- "${witness_paths[@]}"
      fi
    fi
    if [[ -n "$reference" ]]; then
      witnessed_digest="$(jq -er '.artifact_sha256 | select(type == "string" and test("^[0-9a-f]{64}$"))' "$rebuild_dir/$reference")" || {
        echo "Refusing append rebuild: witnessed health digest is missing or invalid in $reference." >&2
        exit 1
      }
      accepted_digest="$(sha256sum "$rebuild_dir/health/latest.json")"
      accepted_digest="${accepted_digest%% *}"
      if [[ "$witnessed_digest" != "$accepted_digest" ]]; then
        echo "Refusing append rebuild: health artifact changed since this candidate was witnessed; resubmit (witnessed $witnessed_digest, accepted health $accepted_digest)." >&2
        exit 1
      fi
    fi
    generation=(python3 scripts/gen_attestations.py --root . --private-key "$DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" --now "$published_at" --force-append)
    [[ -z "$reference" ]] || generation+=(--rekor-reference "$reference")
    (cd "$rebuild_dir" && "${generation[@]}") || {
      echo "Refusing append rebuild: candidate from $old_parent_head at $old_parent could not extend accepted head $new_parent_head at $new_base." >&2
      exit 1
    }
  fi

  # The child submits exactly once. A second main move is a refusal, not a loop.
  suffix=""
  [[ -z "$old_pr" ]] || suffix="${new_base:0:12}"
  (cd "$rebuild_dir" && APPEND_REBUILD_ATTEMPT=1 \
    APPEND_REBUILD_SUFFIX="$suffix" bash "$script") || {
    echo "Refusing append rebuild: candidate from $old_parent_head at $old_parent could not extend accepted head $new_parent_head at $new_base." >&2
    exit 1
  }
  if [[ -n "$old_pr" ]]; then
    current_pr="$(gh pr view "$old_pr" --json number,headRefName,headRefOid,baseRefName,state)"
    jq -e --arg branch "$old_branch" --arg sha "$old_sha" \
      '.state == "OPEN" and .baseRefName == "main" and .headRefName == $branch and .headRefOid == $sha' \
      <<<"$current_pr" >/dev/null || {
      echo "Refusing to retire PR #$old_pr: its identity changed after replacement was filed." >&2
      exit 1
    }
    gh pr close "$old_pr"
  fi
  echo "append rebased onto the accepted head $new_parent_head at $new_base (old $old_parent_head at $old_parent)"
}
expected_source="$(git rev-parse HEAD)"
if [[ -z "$old_pr" ]]; then
  path_output="$(python3 scripts/verify_attestation_append.py --base "$expected_source" --print-paths)"
  [[ -n "$path_output" ]] || { write_noop_result; exit 0; }
  readarray -t old_paths <<<"$path_output"
  old_parent="$expected_source"
  binding_path="$(python3 - <<'PY'
from pathlib import Path
from scripts.attestation_sets import discovery
index = discovery(Path.cwd())
print(index['heads'][index['current_head']].rsplit('/', 1)[0] + '/binding.json')
PY
)"
  binding="$(cat "$binding_path")"
else
  current_pr="$(gh pr view "$old_pr" --json number,headRefName,headRefOid,baseRefName,state)"
  jq -e --arg branch "$old_branch" --arg sha "$old_sha" \
    '.state == "OPEN" and .baseRefName == "main" and .headRefName == $branch and .headRefOid == $sha' \
    <<<"$current_pr" >/dev/null || {
    echo "Refusing rebuild: PR #$old_pr no longer identifies open branch $old_branch at $old_sha." >&2
    exit 1
  }
  git fetch origin "refs/heads/$old_branch:refs/remotes/origin/$old_branch"
  [[ "$(git rev-parse "origin/$old_branch")" == "$old_sha" ]] || {
    echo "Refusing rebuild: PR #$old_pr head changed from $old_sha." >&2
    exit 1
  }
  old_parent="$(git rev-parse "$old_sha^")"
  mapfile -d '' -t old_paths < <(git diff --diff-filter=A --name-only -z "$old_parent" "$old_sha" -- attestations)
  binding_paths=()
  for path in "${old_paths[@]}"; do
    [[ "$path" == attestations/*/revisions/*/binding.json ]] && binding_paths+=("$path")
  done
  (( ${#binding_paths[@]} == 1 )) || {
    echo "Refusing rebuild: PR #$old_pr has ${#binding_paths[@]} new immutable bindings, expected one." >&2
    exit 1
  }
  binding="$(git show "$old_sha:${binding_paths[0]}")"
fi
git fetch origin main
new_base="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$old_parent" "$new_base" || {
  echo "Refusing append rebuild: old base $old_parent is not an ancestor of accepted main $new_base." >&2
  exit 1
}
if [[ "$new_base" != "$old_parent" ]]; then
  old_parent_head="$(git show "$old_parent:attestations/chain-index.json" | jq -er '.current_head')"
  new_parent_head="$(git show "$new_base:attestations/chain-index.json" | jq -er '.current_head')"
  [[ "${APPEND_REBUILD_ATTEMPT:-0}" != 1 ]] || {
    echo "Refusing a second append rebuild: accepted main moved from $old_parent to $new_base (heads $old_parent_head and $new_parent_head)." >&2
    exit 1
  }
  rebuild_from_main "$old_parent" "$new_base" "$old_parent_head" "$new_parent_head" "$binding" "${old_paths[@]}"
  exit 0
fi
[[ -z "$old_pr" ]] || {
  echo "Refusing rebuild: PR #$old_pr still extends accepted Git head $new_base; failure has another cause." >&2
  exit 1
}
python3 scripts/verify_attestation_append.py --base "$expected_source"
if ! jq -e '.claims.rekor_witnessed == true' attestations/latest/binding.json >/dev/null; then
  if [[ "${DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION:-}" != "1" ]]; then
    echo 'Refusing append submission: its binding declares rekor_witnessed: false; a Rekor witness is required. Only an explicit DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION=1 permits unwitnessed publication.' >&2
    exit 1
  fi
fi
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
[[ -z "${APPEND_REBUILD_SUFFIX:-}" ]] || branch="${branch}-${APPEND_REBUILD_SUFFIX}"
# Check the freshly fetched accepted parent without rewriting a signed candidate.
path_output="$(python3 scripts/verify_attestation_append.py --base origin/main --print-paths)"
[[ -n "$path_output" ]] || { write_noop_result; exit 0; }
readarray -t paths <<<"$path_output"
(( ${#paths[@]} )) || { write_noop_result; exit 0; }
parent_head="$(git show "$new_base:attestations/chain-index.json" | jq -er '.current_head | select(type == "string" and test("^[0-9a-f]{64}$"))')"
successor_path="$(write_successor_record "$parent_head" "$head")"
paths+=("$successor_path")
git config user.name github-actions[bot]
git config user.email 41898282+github-actions[bot]@users.noreply.github.com
git switch -c "$branch"
# Only this finalized append's evidence enters Git. Discovery and publication
# projections are derived after acceptance, so concurrent commits share no writes.
git add -- "${paths[@]}"
git diff --cached --quiet && { write_noop_result; exit 0; }
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
if [[ -n "${APPEND_SUBMISSION_RESULT:-}" ]]; then
  printf '%s %s %s\n' "$branch" "$(git rev-parse HEAD)" "${APPEND_REBUILD_ATTEMPT:-0}" > "$APPEND_SUBMISSION_RESULT"
fi
