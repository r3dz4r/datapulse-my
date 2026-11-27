#!/usr/bin/env bash
#
# derive-on-merge: derive the generated surfaces on the merge result instead of
# requiring a change to carry them.
#
# The health pipeline rewrites the eight paths below on main every cycle (about
# every 46 minutes). A change that has to carry them is stale within one cadence
# period, and a conflicting pull request runs no checks at all. So no change
# carries them: this script derives them from the tree under test before any gate
# judges them, and the health pipeline remains their only writer on main.
#
# The invariant "committed derived surfaces match committed source" is held here,
# on the tree under test, for every one of these paths the change itself touches:
# its committed bytes must be exactly what derivation yields from that tree's
# source. A hand edit therefore fails, and so does a regenerated copy that has
# gone stale against the merge base. Paths the change does not touch keep their
# base bytes in git and are replaced in the workspace by their derivation, so
# every later gate judges the merge result as it will be once derived.
#
# This script never commits, stages, or pushes. It writes only the derived paths
# in the working tree, so it cannot contend with the health pipeline for them.
#
# Usage:
#   scripts/derive_on_merge.sh list
#   scripts/derive_on_merge.sh derive
#   scripts/derive_on_merge.sh check --base <commit>
#   scripts/derive_on_merge.sh check --all
set -Eeuo pipefail

# Pure functions of committed source: derived in place, byte-for-byte.
DERIVED_PATHS=(
  health/latest.json
  catalog-snapshot.json
  changelog.json
  catalog-graph.json
  README.md
)
# A pure function of committed source except for its wall-clock generated_at
# stamp: verified with that one field set aside, never rewritten here.
CLOCKED_PATHS=(datapulse_summary.json)
# Derived from health/history.jsonl, which is gitignored and exists only where the
# health pipeline runs. They cannot be re-derived from a checkout, so only the
# health pipeline writes them; a checkout-side gate has nothing to compare against.
WRITER_ONLY_PATHS=(health/trends.json health/drift.json)
OWNED_PATHS=("${DERIVED_PATHS[@]}" "${CLOCKED_PATHS[@]}" "${WRITER_ONLY_PATHS[@]}")

PYTHON="${PYTHON:-python3}"

usage() {
  sed -n '/^# Usage:/,/^set -Eeuo/p' "$0" | sed '$d; s/^# \{0,1\}//'
}

die() {
  printf 'derive_on_merge.sh: %s\n' "$*" >&2
  exit 2
}

contains() {
  local needle="$1" item
  shift
  for item in "$@"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

# Derive every DERIVED_PATHS member in place, in the order the safety net uses.
derive() {
  "$PYTHON" scripts/gen_health_trust_summary.py
  # Writes catalog-snapshot.json and its deprecated alias changelog.json.
  "$PYTHON" scripts/gen_catalog_snapshot.py
  "$PYTHON" scripts/gen_catalog_graph.py
  "$PYTHON" scripts/gen_readme.py
}

digest() {
  sha256sum -- "${DERIVED_PATHS[@]}"
}

# Exit 0 when the committed datapulse_summary.json matches a fresh derivation from
# this tree, comparing every field except the generated_at wall-clock stamp.
clocked_summary_matches() {
  local scratch status=0
  scratch="$(mktemp -d)"
  mkdir -p "$scratch/health"
  cp health/latest.json "$scratch/health/latest.json"
  if [[ -f mcp.json ]]; then
    cp mcp.json "$scratch/mcp.json"
  fi
  "$PYTHON" scripts/gen_public_summary.py --root "$scratch" >/dev/null || status=$?
  if (( status == 0 )); then
    git show HEAD:datapulse_summary.json > "$scratch/committed.json"
    "$PYTHON" - "$scratch/committed.json" "$scratch/datapulse_summary.json" <<'PY' || status=$?
import json
import sys

committed, derived = (json.loads(open(path, encoding="utf-8").read()) for path in sys.argv[1:3])
for document in (committed, derived):
    if not isinstance(document, dict) or "generated_at" not in document:
        raise SystemExit(1)
    document.pop("generated_at")
raise SystemExit(0 if committed == derived else 1)
PY
  fi
  rm -r -- "$scratch"
  return "$status"
}

check() {
  local mode="" base="" path
  while (( $# > 0 )); do
    case "$1" in
      --base)
        (( $# >= 2 )) || die '--base requires a commit'
        mode=base
        base="$2"
        shift 2
        ;;
      --all)
        mode=all
        shift
        ;;
      *) die "unknown check argument: $1" ;;
    esac
  done
  [[ -n "$mode" ]] || die 'check requires --base <commit> or --all'

  # Judge committed bytes only: a locally modified owned path would be judged as
  # if it were the change, so refuse instead of guessing.
  if ! git diff --quiet HEAD -- "${OWNED_PATHS[@]}"; then
    die "working tree differs from HEAD on a derived path; check judges committed bytes only"
  fi

  local touched=() changed
  if [[ "$mode" == base ]]; then
    git rev-parse --verify --quiet "${base}^{commit}" >/dev/null || die "base is not a commit: $base"
    changed="$(git diff --no-renames --name-only "$base" HEAD -- "${OWNED_PATHS[@]}")"
    [[ -z "$changed" ]] || mapfile -t touched <<< "$changed"
    printf 'derive-on-merge: base %s; derived paths this change touches: %s\n' \
      "$(git rev-parse --short "$base")" "${touched[*]:-(none)}"
  else
    touched=("${OWNED_PATHS[@]}")
    printf 'derive-on-merge: no base; judging every derived path\n'
  fi

  derive
  local first second
  first="$(digest)"
  derive
  second="$(digest)"
  if [[ "$first" != "$second" ]]; then
    printf '::error title=derive-on-merge not idempotent::a second derivation changed bytes\n' >&2
    printf 'first run:\n%s\nsecond run:\n%s\n' "$first" "$second" >&2
    exit 1
  fi
  printf 'derive-on-merge: derivation is idempotent across two runs\n'

  local failures=0
  for path in "${touched[@]}"; do
    [[ -n "$path" ]] || continue
    if contains "$path" "${DERIVED_PATHS[@]}"; then
      if git diff --quiet HEAD -- "$path"; then
        printf 'derive-on-merge: %s matches its derivation\n' "$path"
      else
        failures=$((failures + 1))
        printf '::error file=%s,title=derive-on-merge::%s is generated, and the committed bytes are not what its generator yields from this tree. Generated surfaces are derived on merge: drop %s from the change, and change its source or generator instead.\n' \
          "$path" "$path" "$path" >&2
        git --no-pager diff --stat HEAD -- "$path" >&2
      fi
    elif contains "$path" "${CLOCKED_PATHS[@]}"; then
      if clocked_summary_matches; then
        printf 'derive-on-merge: %s matches its derivation (generated_at set aside)\n' "$path"
      else
        failures=$((failures + 1))
        printf '::error file=%s,title=derive-on-merge::%s is generated, and apart from generated_at the committed bytes are not what gen_public_summary.py yields from this tree. Drop %s from the change.\n' \
          "$path" "$path" "$path" >&2
      fi
    else
      printf 'derive-on-merge: %s is written only by the health pipeline from gitignored history; a checkout cannot re-derive it\n' "$path"
    fi
  done
  if (( failures > 0 )); then
    printf 'derive-on-merge: %d generated path(s) disagree with their source\n' "$failures" >&2
    exit 1
  fi
  printf 'derive-on-merge: merge result derived; every touched derivable path matches its source\n'
}

command="${1:-}"
(( $# > 0 )) && shift
case "$command" in
  list)
    (( $# == 0 )) || die 'list takes no arguments'
    printf '%s\n' "${OWNED_PATHS[@]}"
    ;;
  derive)
    (( $# == 0 )) || die 'derive takes no arguments'
    derive
    ;;
  check) check "$@" ;;
  -h|--help) usage ;;
  *)
    usage >&2
    exit 2
    ;;
esac
