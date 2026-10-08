#!/usr/bin/env bash
set -euo pipefail

fixture="$(mktemp -d -p . .generate-aggregate-test.XXXXXX)"
trap 'rm -r "$fixture"' EXIT
mkdir -p "$fixture/scripts"
cp scripts/generate.sh "$fixture/scripts/generate.sh"

# Replace a profile only in the temporary runner so the real profiles stay intact.
python3 - "$fixture/scripts/generate.sh" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
start = source.index('case "$profile" in\n  health-cycle)')
end = source.index('    ;;\n  release-build)', start) + len('    ;;')
synthetic = '''case "$profile" in
  health-cycle)
    description="Synthetic failure aggregation profile"
    generators=("public_surface_preflight" "middle.sh" "fail_last.sh")
    outputs=("first" "middle" "last")
    ;;'''
path.write_text(source[:start] + synthetic + source[end:])
PY

cat > "$fixture/scripts/gen_mcp_reference.py" <<'PY'
import os
import sys

print("first-step-output", flush=True)
if os.environ.get("TEST_FAIL_STEPS") == "1":
    print("first-failure-visible", file=sys.stderr)
    raise SystemExit(7)
PY
for script in gen_llms_summary.py gen_public_discovery.py gen_readme.py verify_distribution_sync.py; do
  printf 'print("later-preflight-command-ran")\n' > "$fixture/scripts/$script"
done
cat > "$fixture/scripts/middle.sh" <<'SH'
printf 'middle-step-ran\n'
SH
cat > "$fixture/scripts/fail_last.sh" <<'SH'
printf 'last-step-output\n'
if [[ "${TEST_FAIL_STEPS:-0}" == 1 ]]; then
  printf 'last-failure-visible\n' >&2
  exit 9
fi
SH

if failure_output=$(cd "$fixture" && TEST_FAIL_STEPS=1 bash scripts/generate.sh health-cycle 2>&1); then
  printf 'FAIL: failing profile exited zero\n' >&2
  exit 1
else
  failure_status=$?
fi
printf '%s\n' "$failure_output"
[[ "$failure_status" -ne 0 ]]
[[ "$failure_output" == *'Failures (2):'* ]]
[[ "$failure_output" == *'first-failure-visible'* ]]
[[ "$failure_output" != *'later-preflight-command-ran'* ]]
[[ "$failure_output" == *'middle-step-ran'* ]]
[[ "$failure_output" == *'last-failure-visible'* ]]
[[ "$failure_output" == *'Dependent steps were attempted'* ]]
[[ "$failure_output" == *'  Step 1: python3 scripts/gen_mcp_reference.py --validate-only'* ]]
[[ "$failure_output" == *'scripts/verify_distribution_sync.py (exit 7)'* ]]
[[ "$failure_output" == *'Step 3: DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" bash scripts/fail_last.sh (exit 9)'* ]]
reported_count=$(grep -c '^  Step ' <<< "$failure_output")
[[ "$reported_count" -eq 2 ]]
printf 'PASS: injected 2 failures; runner reported %s after attempting all 3 steps (exit %s)\n' "$reported_count" "$failure_status"

success_output=$(cd "$fixture" && TEST_FAIL_STEPS=0 bash scripts/generate.sh health-cycle 2>&1)
printf '%s\n' "$success_output"
[[ "$success_output" == *'middle-step-ran'* ]]
[[ "$success_output" == *'later-preflight-command-ran'* ]]
[[ "$success_output" != *'Failures ('* ]]
printf 'PASS: successful profile exited 0 and reported no failures\n'
