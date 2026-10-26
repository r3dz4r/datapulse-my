#!/bin/bash
# Read-only pre-merge refusal: a skipped push check cannot prove PR verification.
set -Eeuo pipefail
trap 'echo "Gate tooling failure: GitHub query or response processing failed" >&2; exit 2' ERR

if [[ $# -lt 1 || $# -gt 2 || ! "$1" =~ ^[1-9][0-9]*$ || -z "${2-default}" ]]; then
  echo "Usage: $0 PR_NUMBER [CONTEXT (default: deterministic-safety-net)]" >&2
  exit 2
fi
pr_number="$1"
context="${2-deterministic-safety-net}"
for tool in gh jq; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Gate tooling failure: $tool is required" >&2
    exit 2
  fi
done

# Resolve the current head rather than accepting a check from an earlier PR revision.
head_sha="$(gh api "repos/{owner}/{repo}/pulls/$pr_number" --jq '.head.sha')"
if [[ ! "$head_sha" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "Gate tooling failure: invalid PR head SHA in GitHub response" >&2
  exit 2
fi
checks="$(gh api "repos/{owner}/{repo}/commits/$head_sha/check-runs?filter=all&per_page=100" --paginate --slurp)"
runs="$(gh api "repos/{owner}/{repo}/actions/runs?head_sha=$head_sha&per_page=100" --paginate --slurp)"

# Check runs do not carry the trigger event. The workflow run's suite ID is the
# authoritative association; a name or details_url alone cannot establish it.
observed="$(jq -cn --argjson checks "$checks" --argjson runs "$runs" \
  --arg context "$context" --arg head "$head_sha" '
  if ($checks | type) != "array" or ($runs | type) != "array" then
    error("expected paginated GitHub responses")
  elif any($checks[]; (.check_runs | type) != "array") or
       any($runs[]; (.workflow_runs | type) != "array") then
    error("missing check_runs or workflow_runs in GitHub response")
  else
    [$checks[].check_runs[] | select(.name == $context) | . as $check |
      ([$runs[].workflow_runs[] |
        select(.check_suite_id == $check.check_suite.id and .head_sha == $head)] | .[0]) as $run |
      {id, status, conclusion, head_sha, event: ($run.event // "unknown")}]
  end
')"

if jq -e --arg head "$head_sha" '
  any(.[]; .head_sha == $head and .event == "pull_request" and
    .status == "completed" and (.conclusion == "success" or .conclusion == "neutral"))
' <<< "$observed" >/dev/null; then
  printf 'Gate satisfied: %s on PR #%s head %s (pull_request)\n' "$context" "$pr_number" "$head_sha"
  exit 0
fi

printf 'Gate refused: %s on PR #%s head %s\n' "$context" "$pr_number" "$head_sha" >&2
jq -r '
  if length == 0 then "  absent: no matching check runs"
  else .[] | "  check=\(.id) event=\(.event) status=\(.status // "unknown") conclusion=\(.conclusion // "none") head=\(.head_sha // "unknown")"
  end
' <<< "$observed" >&2
exit 3
