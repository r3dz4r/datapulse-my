#!/usr/bin/env bash
# Close redundant PRs only after their exact immutable blobs are accepted.
# The attestation store is read-only; independent sets and forks are retained.
set -Eeuo pipefail

if [[ "${APPEND_CLEANUP_BOUNDED:-0}" != 1 ]]; then
  export APPEND_CLEANUP_BOUNDED=1
  exec timeout -k 5s 120s bash "$0" "$@"
fi
deadline=$((SECONDS + 110))
named_timeout() {
  local cap="$1"
  shift
  timeout -k 5s "${cap}s" "$@"
}
retry_timeout() {
  local cap="$1" status output
  shift
  while :; do
    if output="$(named_timeout "$cap" "$@")"; then
      printf '%s\n' "$output"
      return 0
    else
      status=$?
    fi
    if [[ "$status" != 124 && "$status" != 137 ]] || (( SECONDS >= deadline )); then
      return "$status"
    fi
    echo 'Retrying capped superseded-append lookup within cleanup budget.' >&2
  done
}

accepted_number="${1:-}"
protected_number="${2:-}"
[[ -z "$protected_number" || "$protected_number" =~ ^[1-9][0-9]*$ ]]
if [[ -z "$accepted_number" ]]; then
  # Recovery after deferral: the accepted PR is no longer in the open list.
  merged="$(retry_timeout 20 gh pr list --repo "$GITHUB_REPOSITORY" --state merged --limit 1000 \
    --json number,headRefName,baseRefName,mergedAt)"
  accepted_number="$(named_timeout 10 jq -r \
    '[.[] | select(.baseRefName == "main" and (.headRefName | startswith("attestation/append-")))] | sort_by(.mergedAt) | last | .number // empty' <<< "$merged")"
  [[ -n "$accepted_number" ]] || exit 0
fi
[[ "$accepted_number" =~ ^[1-9][0-9]*$ ]]
accepted="$(retry_timeout 20 gh pr view "$accepted_number" --repo "$GITHUB_REPOSITORY" \
  --json number,headRefName,baseRefName,isCrossRepository,state,createdAt,mergeCommit)"
named_timeout 10 jq -e --argjson number "$accepted_number" \
  '.number == $number and .state == "MERGED" and .baseRefName == "main" and .isCrossRepository == false
   and (.headRefName | startswith("attestation/append-"))' <<< "$accepted" >/dev/null
merge_sha="$(named_timeout 10 jq -er '.mergeCommit.oid' <<< "$accepted")"
[[ "$merge_sha" =~ ^[0-9a-f]{40}$ ]]
retry_timeout 30 git fetch origin refs/heads/main:refs/remotes/origin/main
named_timeout 10 git merge-base --is-ancestor "$merge_sha" origin/main

open_prs="$(retry_timeout 20 gh pr list --repo "$GITHUB_REPOSITORY" --state open --limit 1000 \
  --json number,headRefName,headRefOid,baseRefName,createdAt,isCrossRepository)"
[[ "$(named_timeout 10 jq 'length' <<< "$open_prs")" -lt 1000 ]]
numbers="$(named_timeout 10 jq -r --argjson accepted "$accepted" --arg protected "$protected_number" \
  '.[] | select(.number != $accepted.number and .createdAt < $accepted.createdAt
    and (.number | tostring) != $protected
    and .baseRefName == "main" and .isCrossRepository == false
    and (.headRefName | startswith("attestation/append-"))) | .number' <<< "$open_prs")"
while IFS= read -r number; do
  [[ -n "$number" ]] || continue
  [[ "$number" != "$accepted_number" && "$number" != "$protected_number" && "$number" =~ ^[1-9][0-9]*$ ]]
  files="$(retry_timeout 20 gh api "repos/$GITHUB_REPOSITORY/pulls/$number/files" --paginate --slurp)"
  # GitHub caps a PR file response at 3000. Incomplete metadata cannot prove
  # redundancy. A shared date or parent also cannot prove it.
  if ! named_timeout 10 jq -e '
    add | length > 0 and length < 3000
    and any(.[]; .filename | endswith("/chain_head.json"))
    and all(.[]; .status == "added" and (.sha | test("^[0-9a-f]{40}$"))
      and (.filename | test("^attestations/([0-9]{4}-[0-9]{2}-[0-9]{2}/(sets|revisions)/[0-9a-f]{64}/[A-Za-z0-9_.-]+\\.json(\\.gz)?|rekor/[0-9]{4}-[0-9]{2}-[0-9]{2}/(health\\.[0-9a-f]{64}\\.(statement|sigstore\\.bundle)|reference\\.[0-9a-f]{64})\\.json)$")))
    ' <<< "$files" >/dev/null; then
    continue
  fi
  entries="$(named_timeout 10 jq -r 'add | .[] | [.filename, .sha] | @tsv' <<< "$files")"
  redundant=true
  while IFS=$'\t' read -r path blob; do
    if ! accepted_blob="$(named_timeout 10 git rev-parse --verify "origin/main:$path")" \
      || [[ "$accepted_blob" != "$blob" ]]; then
      redundant=false
      break
    fi
  done <<< "$entries"
  [[ "$redundant" == true ]] || continue
  # Recheck identity immediately before closing; never delete its branch.
  current="$(retry_timeout 20 gh pr view "$number" --repo "$GITHUB_REPOSITORY" \
    --json number,headRefName,headRefOid,baseRefName,isCrossRepository,state,createdAt)"
  original="$(named_timeout 10 jq -c --argjson number "$number" '.[] | select(.number == $number)' <<< "$open_prs")"
  if named_timeout 10 jq -e --argjson original "$original" --argjson accepted "$accepted_number" \
    '.number != $accepted and .number == $original.number and .state == "OPEN"
     and .headRefName == $original.headRefName and .headRefOid == $original.headRefOid
     and .createdAt == $original.createdAt and .baseRefName == "main" and .isCrossRepository == false' \
    <<< "$current" >/dev/null; then
    named_timeout 20 gh pr close "$number" --repo "$GITHUB_REPOSITORY"
    echo "Closed superseded append PR #$number after acceptance of #$accepted_number; all immutable blobs are on main."
  fi
done <<< "$numbers"
