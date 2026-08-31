#!/usr/bin/env bash
# Regression coverage for the local OpenWiki snapshot runner.  This script uses
# throwaway repositories and stubs so it never invokes the paid OpenWiki API.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
RUNNER="$ROOT/scripts/run_openwiki_snapshot.sh"
TEST_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/datapulse-openwiki-snapshot-test.XXXXXX")
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

make_repo() {
  local repo=$1
  mkdir -p "$repo/scripts" "$repo/tools/openwiki" "$repo/openwiki" "$repo/bin"
  cp "$RUNNER" "$repo/scripts/run_openwiki_snapshot.sh"
  chmod +x "$repo/scripts/run_openwiki_snapshot.sh"
  printf '{}\n' >"$repo/tools/openwiki/package.json"
  printf '{"lockfileVersion": 3}\n' >"$repo/tools/openwiki/package-lock.json"
  for page in quickstart.md datasets.md mcp.md operations.md; do
    printf 'old %s\n' "$page" >"$repo/openwiki/$page"
  done
  printf '{"old": true}\n' >"$repo/openwiki/.last-update.json"
  printf 'keep me\n' >"$repo/openwiki/unowned.md"
  printf '#!/usr/bin/env bash\nexit 0\n' >"$repo/scripts/inject_openwiki_canonical_facts.py"
  printf '#!/usr/bin/env bash\nif [[ ${OPENWIKI_TEST_VERIFY_FAIL:-0} == 1 && $* == *--generated* ]]; then exit 23; fi\nexit 0\n' >"$repo/scripts/verify_openwiki.py"
  chmod +x "$repo/scripts/inject_openwiki_canonical_facts.py" "$repo/scripts/verify_openwiki.py"
  git -C "$repo" init -q
  git -C "$repo" config user.email test@example.invalid
  git -C "$repo" config user.name snapshot-test
  git -C "$repo" add .
  git -C "$repo" commit -qm initial
}

write_npm_stub() {
  local repo=$1
  cat >"$repo/bin/python3" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
if [[ ${OPENWIKI_TEST_VERIFY_FAIL:-0} == 1 && $(cd "$(dirname "$1")/.." && pwd) == "$OPENWIKI_TEST_TARGET" && $* == *--generated* ]]; then
  exit 23
fi
exit 0
STUB
  chmod +x "$repo/bin/python3"
  cat >"$repo/bin/npm" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
if [[ $* == *' exec '* || $1 == exec || $* == *'openwiki code --update --print'* ]]; then
  snapshot=''
  for arg in "$@"; do
    if [[ $arg == --prefix ]]; then
      continue
    fi
    if [[ $arg == */tools/openwiki ]]; then snapshot=${arg%/tools/openwiki}; fi
  done
  [[ -n $snapshot ]] || exit 41
  [[ -n ${OPENWIKI_TEST_CWD_LOG:-} ]] && printf '%s\n' "$PWD" >"$OPENWIKI_TEST_CWD_LOG"
  printf '{"cwd":"%s"}\n' "$PWD" >"$PWD/openwiki/.run.json"
  for page in quickstart.md datasets.md mcp.md operations.md; do
    printf 'new %s\n' "$page" >"$snapshot/openwiki/$page"
  done
  printf '{"new": true}\n' >"$snapshot/openwiki/.last-update.json"
  printf 'snapshot-only\n' >"$snapshot/openwiki/unowned-generated.md"
  if [[ ${OPENWIKI_TEST_GENERATION_FAIL:-0} == 1 ]]; then
    exit 42
  fi
  if [[ ${OPENWIKI_TEST_DRIFT:-} == health ]]; then
    mkdir -p "$OPENWIKI_TEST_TARGET/health"
    printf 'health\n' >"$OPENWIKI_TEST_TARGET/health/latest.json"
    git -C "$OPENWIKI_TEST_TARGET" add health/latest.json
    git -C "$OPENWIKI_TEST_TARGET" commit -qm health-cycle
  elif [[ ${OPENWIKI_TEST_DRIFT:-} == code ]]; then
    printf 'code drift\n' >"$OPENWIKI_TEST_TARGET/source.py"
    git -C "$OPENWIKI_TEST_TARGET" add source.py
    git -C "$OPENWIKI_TEST_TARGET" commit -qm source-drift
  fi
fi
STUB
  chmod +x "$repo/bin/npm"
}

run_case() {
  local repo=$1
  shift
  PATH="$repo/bin:$PATH" OPENWIKI_TEST_TARGET="$repo" "$@" bash "$repo/scripts/run_openwiki_snapshot.sh"
}

repo="$TEST_ROOT/generation-failure"
make_repo "$repo"
write_npm_stub "$repo"
target_head=$(git -C "$repo" rev-parse HEAD)
target_status=$(git -C "$repo" status --porcelain)
target_metadata=$(git -C "$repo" hash-object openwiki/.last-update.json)
if run_case "$repo" env OPENWIKI_TEST_GENERATION_FAIL=1 OPENWIKI_TEST_CWD_LOG="$TEST_ROOT/generation-failure.cwd" >"$TEST_ROOT/generation-failure.output" 2>&1; then
  fail 'accepted a generation failure'
fi
[[ $(<"$TEST_ROOT/generation-failure.cwd") != "$repo" ]] || fail 'OpenWiki ran from the target checkout'
[[ $(<"$TEST_ROOT/generation-failure.cwd") == "${TMPDIR:-/tmp}/datapulse-openwiki-snapshot-"* ]] || fail 'OpenWiki did not run from the detached snapshot'
[[ $(git -C "$repo" rev-parse HEAD) == "$target_head" ]] || fail 'generation failure changed target HEAD'
[[ $(git -C "$repo" status --porcelain) == "$target_status" ]] || fail 'generation failure dirtied the target tree'
[[ $(git -C "$repo" hash-object openwiki/.last-update.json) == "$target_metadata" ]] || fail 'generation failure modified target metadata'
[[ ! -e "$repo/openwiki/.run.json" ]] || fail 'generation failure wrote target run metadata'

repo="$TEST_ROOT/success"
make_repo "$repo"
write_npm_stub "$repo"
target_head=$(git -C "$repo" rev-parse HEAD)
run_case "$repo" env OPENWIKI_TEST_CWD_LOG="$TEST_ROOT/success.cwd"
[[ $(<"$TEST_ROOT/success.cwd") != "$repo" ]] || fail 'successful OpenWiki ran from the target checkout'
[[ $(<"$TEST_ROOT/success.cwd") == "${TMPDIR:-/tmp}/datapulse-openwiki-snapshot-"* ]] || fail 'successful OpenWiki did not run from the detached snapshot'
[[ $(git -C "$repo" rev-parse HEAD) == "$target_head" ]] || fail 'successful snapshot verification changed target HEAD'
[[ ! -e "$repo/openwiki/.run.json" ]] || fail 'successful generation wrote target run metadata'
for page in quickstart.md datasets.md mcp.md operations.md; do
  [[ $(<"$repo/openwiki/$page") == "new $page" ]] || fail "did not promote $page"
done
[[ $(<"$repo/openwiki/.last-update.json") == '{"new": true}' ]] || fail 'did not promote .last-update.json'
[[ $(<"$repo/openwiki/unowned.md") == 'keep me' ]] || fail 'promoted unowned output'
[[ ! -e "$repo/openwiki/unowned-generated.md" ]] || fail 'promoted snapshot-only output'
[[ ! -e "${TMPDIR:-/tmp}/datapulse-openwiki-snapshot-$(git -C "$repo" rev-parse HEAD)" ]] || fail 'temporary worktree was not cleaned up'

repo="$TEST_ROOT/health-drift"
make_repo "$repo"
write_npm_stub "$repo"
run_case "$repo" env OPENWIKI_TEST_DRIFT=health
[[ $(<"$repo/openwiki/quickstart.md") == 'new quickstart.md' ]] || fail 'did not promote after permitted health drift'

repo="$TEST_ROOT/source-drift"
make_repo "$repo"
write_npm_stub "$repo"
if run_case "$repo" env OPENWIKI_TEST_DRIFT=code >"$repo/output" 2>&1; then
  fail 'accepted source/code drift'
fi
rg -q 'source drift' "$repo/output" || fail 'did not classify source drift'
[[ $(<"$repo/openwiki/quickstart.md") == 'old quickstart.md' ]] || fail 'promoted after source drift'

repo="$TEST_ROOT/dirty-target"
make_repo "$repo"
write_npm_stub "$repo"
printf 'operator change\n' >>"$repo/openwiki/quickstart.md"
if run_case "$repo" env >"$repo/output" 2>&1; then
  fail 'accepted dirty target OpenWiki path'
fi
rg -q 'dirty target OpenWiki path' "$repo/output" || fail 'did not report dirty target refusal'

repo="$TEST_ROOT/verifier-failure"
make_repo "$repo"
write_npm_stub "$repo"
if run_case "$repo" env OPENWIKI_TEST_VERIFY_FAIL=1 >"$repo/output" 2>&1; then
  fail 'hid target verifier failure'
fi
rg -q 'target promotion failed' "$repo/output" || fail 'did not report target verifier failure'
[[ $(<"$repo/openwiki/quickstart.md") == 'old quickstart.md' ]] || fail 'did not restore target after verifier failure'

printf 'OpenWiki snapshot runner regression tests passed\n'
