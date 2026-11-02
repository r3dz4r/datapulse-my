#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/.." && pwd)
source_file="$script_dir/datapulse-pipeline.sh"
destination=/usr/local/sbin/datapulse-pipeline.sh

usage() {
  printf 'Usage: %s [--check]\n' "$0" >&2
  exit 2
}

case "$#" in
  0) ;;
  1) [[ "$1" == --check ]] || usage ;;
  *) usage ;;
esac

if [[ "${1:-}" == --check ]]; then
  if [[ ! -f "$destination" || ! -r "$destination" ]]; then
    printf 'Pipeline destination absent or unreadable: %s\n' "$destination" >&2
    exit 2
  fi
  source_digest=$(sha256sum -- "$source_file")
  source_digest="${source_digest%% *}"
  if ! destination_digest=$(sha256sum -- "$destination"); then
    printf 'Pipeline destination unreadable: %s\n' "$destination" >&2
    exit 2
  fi
  destination_digest="${destination_digest%% *}"
  if [[ "$source_digest" != "$destination_digest" ]]; then
    printf 'Pipeline destination is stale:\n%s  %s\n%s  %s\n' \
      "$source_digest" "$source_file" "$destination_digest" "$destination" >&2
    exit 1
  fi
  printf 'Pipeline destination matches: %s (%s)\n' "$destination" "$source_digest"
  exit 0
fi

if (( EUID != 0 )); then
  printf 'Pipeline installation requires root.\n' >&2
  exit 1
fi
if [[ ! -x "$source_file" ]]; then
  printf 'Pipeline source is not executable: %s\n' "$source_file" >&2
  exit 1
fi
source_changes=$(git -C "$repo_root" status --porcelain -- scripts/datapulse-pipeline.sh)
if [[ -n "$source_changes" ]]; then
  printf 'Pipeline source has uncommitted changes: %s\n' "$source_file" >&2
  exit 1
fi

# Set ownership and mode before the rename exposes the new entrypoint.
temp_file=$(mktemp -- "${destination}.tmp.XXXXXX")
trap 'rm -f -- "$temp_file"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
install -o root -g root -m 755 -- "$source_file" "$temp_file"
mv -fT -- "$temp_file" "$destination"
