#!/usr/bin/env bash
# Regenerate OpenWiki against one immutable revision, then promote only its
# explicitly owned derivative files into a compatible live checkout.
set -euo pipefail

TARGET_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OWNED_PATHS=(
  openwiki/quickstart.md
  openwiki/datasets.md
  openwiki/mcp.md
  openwiki/operations.md
  openwiki/.last-update.json
)
HEALTH_PATHS=(
  'health/**'
  'record-evidence/**/latest.json'
  'attestations/latest/**'
  '.attestations/latest/**'
  '.attestations/chain_head.json'
  catalog-graph.json
  catalog-snapshot.json
  changelog.json
  feed.xml
)
SOURCE_SHA=''
TARGET_SHA=''
TARGET_STATUS_BEFORE=''
SNAPSHOT=''
SNAPSHOT_READY=0

report() {
  printf '%s\n' "$*"
}

fail() {
  printf 'OpenWiki snapshot runner: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ $SNAPSHOT_READY == 1 ]]; then
    git -C "$TARGET_ROOT" worktree remove --force "$SNAPSHOT" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

target_openwiki_is_clean() {
  local path
  for path in "${OWNED_PATHS[@]}"; do
    if [[ -n $(git -C "$TARGET_ROOT" status --porcelain -- "$path") ]]; then
      return 1
    fi
  done
}

health_only_drift() {
  local changed
  local pattern
  while IFS= read -r changed; do
    [[ -z $changed ]] && continue
    for pattern in "${HEALTH_PATHS[@]}"; do
      if [[ $changed == $pattern ]]; then
        continue 2
      fi
    done
    return 1
  done < <(git -C "$TARGET_ROOT" diff --name-only "$SOURCE_SHA" "$TARGET_SHA")
}

discard_snapshot_unowned_changes() {
  local path
  local owned
  while IFS= read -r -d '' path; do
    owned=0
    local candidate
    for candidate in "${OWNED_PATHS[@]}"; do
      [[ $path == "$candidate" ]] && owned=1 && break
    done
    [[ $owned == 1 ]] && continue
    if git -C "$SNAPSHOT" cat-file -e "$SOURCE_SHA:$path" 2>/dev/null; then
      git -C "$SNAPSHOT" restore --source "$SOURCE_SHA" --staged --worktree -- "$path"
    else
      rm -rf -- "$SNAPSHOT/$path"
    fi
  done < <(
    {
      git -C "$SNAPSHOT" diff --name-only -z "$SOURCE_SHA"
      git -C "$SNAPSHOT" ls-files --others --exclude-standard -z
    }
  )
}

load_openwiki_environment() {
  local env_file="$HOME/.openwiki/.env"
  if [[ -f $env_file ]]; then
    # This operator-owned file may contain the API key. Do not echo it.
    set +u
    set -a
    . "$env_file"
    set +a
    set -u
  fi
  export OPENWIKI_PROVIDER=openai
  export OPENWIKI_MODEL_ID=gpt-5.6-luna
  export OPENWIKI_TELEMETRY_DISABLED=1
}

stage_and_promote() {
  local relative destination staged backup current_head
  local -a staged_paths=()
  local -a backup_paths=()
  local -a existed=()

  current_head=$(git -C "$TARGET_ROOT" rev-parse HEAD)
  [[ $current_head == "$TARGET_SHA" ]] \
    || fail 'source drift: target HEAD changed again before promotion'
  target_openwiki_is_clean \
    || fail 'dirty target OpenWiki path(s) appeared before promotion; refusing overwrite'

  for relative in "${OWNED_PATHS[@]}"; do
    [[ -f $SNAPSHOT/$relative ]] || fail "snapshot did not generate required path: $relative"
    destination="$TARGET_ROOT/$relative"
    staged=$(mktemp "$(dirname "$destination")/.${relative##*/}.openwiki-snapshot.XXXXXX")
    cp -- "$SNAPSHOT/$relative" "$staged"
    staged_paths+=("$staged")
    if [[ -e $destination ]]; then
      backup=$(mktemp "$(dirname "$destination")/.${relative##*/}.openwiki-backup.XXXXXX")
      cp -- "$destination" "$backup"
      backup_paths+=("$backup")
      existed+=(1)
    else
      backup_paths+=('')
      existed+=(0)
    fi
  done

  for ((i = 0; i < ${#OWNED_PATHS[@]}; i++)); do
    mv -f -- "${staged_paths[$i]}" "$TARGET_ROOT/${OWNED_PATHS[$i]}"
  done

  if ! (cd "$TARGET_ROOT" && python3 "$TARGET_ROOT/scripts/verify_openwiki.py" --generated --changed-from "$TARGET_SHA"); then
    for ((i = 0; i < ${#OWNED_PATHS[@]}; i++)); do
      if [[ ${existed[$i]} == 1 ]]; then
        mv -f -- "${backup_paths[$i]}" "$TARGET_ROOT/${OWNED_PATHS[$i]}"
      else
        rm -f -- "$TARGET_ROOT/${OWNED_PATHS[$i]}"
      fi
    done
    fail "target promotion failed verification; restored the prior five owned paths"
  fi

  for backup in "${backup_paths[@]}"; do
    [[ -z $backup ]] || rm -f -- "$backup"
  done
}

cd "$TARGET_ROOT"
SOURCE_SHA=$(git rev-parse HEAD) || fail 'cannot resolve target HEAD'
TARGET_STATUS_BEFORE=$(git status --porcelain)
report "SOURCE_SHA=$SOURCE_SHA"
if ! target_openwiki_is_clean; then
  fail 'dirty target OpenWiki path(s); refusing to overwrite partial or operator output'
fi

SNAPSHOT="${TMPDIR:-/tmp}/datapulse-openwiki-snapshot-$SOURCE_SHA"
if [[ -e $SNAPSHOT ]] || git worktree list --porcelain | grep -Fqx "worktree $SNAPSHOT"; then
  fail "snapshot worktree collision: $SNAPSHOT"
fi

git worktree add --detach "$SNAPSHOT" "$SOURCE_SHA"
SNAPSHOT_READY=1
load_openwiki_environment
cd "$SNAPSHOT"
npm ci --prefix "$SNAPSHOT/tools/openwiki"
npm exec --prefix "$SNAPSHOT/tools/openwiki" -- openwiki code --update --print
python3 "$SNAPSHOT/scripts/inject_openwiki_canonical_facts.py" --root "$SNAPSHOT"
discard_snapshot_unowned_changes
python3 "$SNAPSHOT/scripts/verify_openwiki.py" --generated --changed-from "$SOURCE_SHA"
report 'SNAPSHOT_GENERATION=verified'

TARGET_SHA=$(git -C "$TARGET_ROOT" rev-parse HEAD)
report "TARGET_SHA=$TARGET_SHA"
if [[ $TARGET_SHA != "$SOURCE_SHA" ]]; then
  git -C "$TARGET_ROOT" merge-base --is-ancestor "$SOURCE_SHA" "$TARGET_SHA" \
    || fail 'source drift: target HEAD is not a fast-forward-compatible descendant of SOURCE_SHA'
  health_only_drift || fail 'source drift: target changed outside the documented health-cycle ownership set'
fi
if ! target_openwiki_is_clean; then
  fail 'dirty target OpenWiki path(s) appeared during generation; refusing promotion'
fi
[[ $(git -C "$TARGET_ROOT" status --porcelain) == "$TARGET_STATUS_BEFORE" ]] \
  || fail 'source drift: target working tree changed during generation'

stage_and_promote
report "PROMOTED_PATHS=$(IFS=,; echo "${OWNED_PATHS[*]}")"
report 'TARGET_PROMOTION=verified'
