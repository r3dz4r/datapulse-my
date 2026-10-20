#!/usr/bin/env bash
# Restore only the attestation paths that differ from a source revision.
#
# The deploy lane imports accepted evidence from origin/main, then discards
# that overlay before detaching to a newer settled revision. A whole-tree
# `git restore` of the attestation pathspecs walks every tracked file (tens of
# thousands of files, gigabytes at the current tree size) to correct a handful.
# Make the work proportional to the delta instead: ask git which paths differ,
# then restore exactly those in argv-sized batches. The caller keeps its own
# sixty-second bound; this script never widens or bypasses it.
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: restore_attestations.sh --source <git-rev> [--pathspec <path>...]...

Restore worktree paths under the given pathspecs to their content at <git-rev>.
Only paths that differ from <git-rev> are touched. Paths the source revision
lacks (including untracked worktree files) are left exactly as the previous
whole-tree `git restore --source <rev> --worktree` left them.

Defaults: --pathspec attestations --pathspec .attestations/chain_head.json
EOF
}

die() {
  printf 'restore_attestations: %s\n' "$*" >&2
  exit 2
}

source_rev=
pathspecs=()
while (($#)); do
  case "$1" in
    --source)
      (($# >= 2)) || die "--source requires a revision"
      source_rev=$2
      shift 2
      ;;
    --source=*)
      source_rev=${1#*=}
      shift
      ;;
    --pathspec)
      shift
      (($#)) || die "--pathspec requires at least one path"
      while (($#)) && [[ $1 != --* ]]; do
        pathspecs+=("$1")
        shift
      done
      ;;
    --pathspec=*)
      pathspecs+=("${1#*=}")
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ -n $source_rev ]] || die "--source is required"
((${#pathspecs[@]})) || pathspecs=(attestations .attestations/chain_head.json)

# Diff names are repository-root relative; restore them from the same root so a
# caller's working directory cannot change what a pathspec means.
repo_root=$(git rev-parse --show-toplevel 2>/dev/null) \
  || die "not inside a git worktree"
cd "$repo_root"

git rev-parse --verify --quiet "${source_rev}^{commit}" >/dev/null \
  || die "unknown source revision: $source_rev"

tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/restore-attestations.XXXXXX")
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

changed_file="$tmpdir/changed"
# --no-renames matters for equivalence with the old whole-tree restore: rename
# detection would report only the new name, hiding the deleted old path that a
# whole-tree restore still brings back.
if ! git diff --no-renames --name-only -z --diff-filter=ACDMRTUXB \
  "$source_rev" -- "${pathspecs[@]}" > "$changed_file"; then
  die "failed to compute differences from $source_rev"
fi

changed=()
while IFS= read -r -d '' path; do
  changed+=("$path")
done < "$changed_file"

if ((${#changed[@]} == 0)); then
  printf 'No differences to restore from %s over %s.\n' \
    "$source_rev" "${pathspecs[*]}"
  exit 0
fi

batch_size=${RESTORE_ATTESTATIONS_BATCH_SIZE:-200}
[[ $batch_size =~ ^[1-9][0-9]*$ ]] \
  || die "RESTORE_ATTESTATIONS_BATCH_SIZE must be a positive integer"

restored=0
for ((offset = 0; offset < ${#changed[@]}; offset += batch_size)); do
  batch=("${changed[@]:offset:batch_size}")
  git restore --source "$source_rev" --worktree -- "${batch[@]}"
  restored=$((restored + ${#batch[@]}))
done

printf 'Restored %d path(s) from %s in bounded batches.\n' \
  "$restored" "$source_rev" >&2
