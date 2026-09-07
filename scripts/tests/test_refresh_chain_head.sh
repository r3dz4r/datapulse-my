#!/usr/bin/env bash
# Regression coverage for refreshing an already-committed daily attestation.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/datapulse-refresh-chain-head-test.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

write_json() {
  local path=$1
  local contents=$2
  mkdir -p "$(dirname "$path")"
  printf '%s\n' "$contents" >"$path"
}

make_repo() {
  local repo=$1
  local include_dated=$2
  local count=${3:-2}
  mkdir -p "$repo/scripts" "$repo/health" "$repo/.attestations" "$repo/bin"
  cp "$ROOT/scripts/refresh_chain_head.sh" "$repo/scripts/refresh_chain_head.sh"
  chmod +x "$repo/scripts/refresh_chain_head.sh"
  write_json "$repo/health/latest.json" '{"datasets":[{"dataset_id":"one"},{"dataset_id":"two"}]}'
  if [[ "$include_dated" == true ]]; then
    local day
    day="$(date -u +%F)"
    write_json "$repo/attestations/$day/chain_head.json" "{\"payload\":{\"dataset_count\":$count},\"chain_head\":\"fixture-head\"}"
    write_json "$repo/attestations/$day/index.json" '{"fixture":"index"}'
    write_json "$repo/attestations/$day/scores.json" '{"fixture":"scores"}'
    write_json "$repo/attestations/$day/binding.json" '{"fixture":"binding"}'
  fi
  cat >"$repo/bin/python3" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$PWD/generator-invocations"
mkdir -p "$PWD/attestations/latest"
printf '%s\n' '{"payload":{"dataset_count":2},"chain_head":"generated-head"}' >"$PWD/attestations/latest/chain_head.json"
printf '%s\n' '{"fixture":"generated-index"}' >"$PWD/attestations/latest/index.json"
printf '%s\n' '{"fixture":"generated-scores"}' >"$PWD/attestations/latest/scores.json"
printf '%s\n' '{"fixture":"generated-binding"}' >"$PWD/attestations/latest/binding.json"
STUB
  chmod +x "$repo/bin/python3"
}

same_day="$TEST_ROOT/same-day"
make_repo "$same_day" true
same_day_output="$TEST_ROOT/same-day.out"
PATH="$same_day/bin:$PATH" bash "$same_day/scripts/refresh_chain_head.sh" fixture-private-key >"$same_day_output"
[[ ! -e "$same_day/generator-invocations" ]] || fail 'same-day refresh invoked gen_attestations'
rg -q 'already exists; refreshing latest/chain-head from committed set \(no re-sign\)' "$same_day_output"
for name in chain_head.json index.json scores.json binding.json; do
  cmp "$same_day/attestations/$(date -u +%F)/$name" "$same_day/attestations/latest/$name"
done
cmp "$same_day/attestations/latest/chain_head.json" "$same_day/.attestations/chain_head.json"

mismatch="$TEST_ROOT/mismatch"
make_repo "$mismatch" true 3
if PATH="$mismatch/bin:$PATH" bash "$mismatch/scripts/refresh_chain_head.sh" fixture-private-key >"$TEST_ROOT/mismatch.out" 2>"$TEST_ROOT/mismatch.err"; then
  fail 'accepted a committed chain head with a mismatched dataset_count'
fi
[[ ! -e "$mismatch/generator-invocations" ]] || fail 'mismatched same-day refresh invoked gen_attestations'
rg -q 'dataset_count \(3\) does not match canonical health \(2\)' "$TEST_ROOT/mismatch.err"

first_day="$TEST_ROOT/first-day"
make_repo "$first_day" false
PATH="$first_day/bin:$PATH" bash "$first_day/scripts/refresh_chain_head.sh" fixture-private-key
[[ -s "$first_day/generator-invocations" ]] || fail 'first-of-day refresh did not invoke gen_attestations'
[[ "$(jq -r '.chain_head' "$first_day/.attestations/chain_head.json")" == generated-head ]] || fail 'first-of-day refresh did not mirror generated chain head'

printf 'refresh_chain_head.sh tests passed.\n'
