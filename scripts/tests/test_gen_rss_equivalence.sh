#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT

legacy_script="$workspace/gen_rss_legacy.sh"
legacy_feed="$workspace/legacy-feed.xml"
current_feed="$workspace/current-feed.xml"
perturbed_feed="$workspace/perturbed-feed.xml"
health_input="$workspace/latest.json"
manifest_input="$workspace/datapulse.json"

git -C "$repo_root" show HEAD:scripts/gen_rss.sh > "$legacy_script"
chmod +x "$legacy_script"
cp "$repo_root/health/latest.json" "$health_input"
cp "$repo_root/datapulse.json" "$manifest_input"

assert_identical() {
  local expected="$1"
  local actual="$2"

  if cmp -s "$expected" "$actual"; then
    return 0
  fi

  awk '
    NR == FNR { expected[FNR] = $0; expected_lines = FNR; next }
    !(FNR in expected) || expected[FNR] != $0 {
      printf "first differing line %d\nexpected: %s\nactual: %s\n", FNR, expected[FNR], $0 > "/dev/stderr"
      failed = 1
      exit 1
    }
    END {
      if (!failed && FNR != expected_lines) {
        printf "first differing line %d\nexpected: %s\nactual: %s\n", FNR + 1, expected[FNR + 1], "<end of file>" > "/dev/stderr"
        exit 1
      }
    }
  ' "$expected" "$actual"
}

generate_feed() {
  local label="$1"
  local script="$2"
  local destination="$3"
  local started_ns
  local elapsed_ns

  started_ns="$(date +%s%N)"
  (
    cd "$workspace"
    bash "$script" "$health_input" "$manifest_input"
  )
  elapsed_ns=$(( $(date +%s%N) - started_ns ))
  mv "$workspace/feed.xml" "$destination"
  awk -v label="$label" -v elapsed_ns="$elapsed_ns" \
    'BEGIN { printf "%s wall-clock: %.3fs\n", label, elapsed_ns / 1000000000 }'
}

generate_feed "legacy" "$legacy_script" "$legacy_feed"
generate_feed "single-jq" "$repo_root/scripts/gen_rss.sh" "$current_feed"

assert_identical "$legacy_feed" "$current_feed"
printf 'byte-identical comparison: passed\n'

cp "$current_feed" "$perturbed_feed"
printf '\n' >> "$perturbed_feed"
if assert_identical "$current_feed" "$perturbed_feed"; then
  printf 'deliberate perturbation was not detected\n' >&2
  exit 1
fi
printf 'deliberate perturbation detection: passed\n'
