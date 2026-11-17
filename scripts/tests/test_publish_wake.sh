#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
script="$script_dir/../datapulse-publish-wake.sh"
fixture=$(mktemp -d)
trap 'rm -rf -- "$fixture"' EXIT
mkdir -p "$fixture/bin" "$fixture/repo/var/log" "$fixture/elsewhere"
export DATAPULSE_REPO="$fixture/repo"
export DATAPULSE_PUBLICATION_STATE="$fixture/repo/var/log/publication-in-flight.sha"
export DATAPULSE_PUBLISH_WAKE_STATE="$fixture/repo/var/log/wake/main.sha"
export DATAPULSE_PUBLISH_UNIT=fixture-publish.service
export WAKE_FIXTURE="$fixture"
export PATH="$fixture/bin:$PATH"
export REMOTE_HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export REMOTE_STATUS=0 START_STATUS=0

cat > "$fixture/bin/git" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$WAKE_FIXTURE/reads"
[[ "$*" == "-C $DATAPULSE_REPO ls-remote --exit-code --refs origin refs/heads/main" ]]
[[ "${GIT_TERMINAL_PROMPT:-}" == 0 ]]
if (( REMOTE_STATUS != 0 )); then
  printf 'fixture remote unavailable\n' >&2
  exit "$REMOTE_STATUS"
fi
printf '%s\trefs/heads/main\n' "$REMOTE_HEAD"
SH
cat > "$fixture/bin/systemctl" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$WAKE_FIXTURE/starts"
[[ "$*" == "--no-block start ${EXPECTED_UNIT:-fixture-publish.service}" ]]
# State must be recorded before the asynchronous request.
[[ "$(cat "${DATAPULSE_PUBLISH_WAKE_STATE:-$DATAPULSE_REPO/var/log/publish-wake-main.sha}")" == "$REMOTE_HEAD" ]]
exit "$START_STATUS"
SH
chmod +x "$fixture/bin/git" "$fixture/bin/systemctl"
[[ "$(command -v git)" == "$fixture/bin/git" ]]
[[ "$(command -v systemctl)" == "$fixture/bin/systemctl" ]]

run_case() {
  local label="$1" expected_reads="$2" expected_starts="$3"
  : > "$fixture/reads"
  : > "$fixture/starts"
  local status=0
  (cd "$fixture/elsewhere" && bash "$script") > "$fixture/out" 2> "$fixture/err" || status=$?
  if (( status != 0 )); then
    cat "$fixture/out" "$fixture/err" >&2
    printf 'FAIL %s: exit=%s\n' "$label" "$status" >&2
    return "$status"
  fi
  local reads starts
  reads=$(wc -l < "$fixture/reads")
  starts=$(wc -l < "$fixture/starts")
  [[ "$reads" -eq "$expected_reads" && "$reads" -le 1 ]]
  [[ "$starts" -eq "$expected_starts" && "$starts" -le 1 ]]
  [[ ! -s "$fixture/out" ]]
  if [[ -f "$fixture/marker-before" ]]; then
    cmp "$fixture/marker-before" "$DATAPULSE_PUBLICATION_STATE"
    [[ "$(stat -c '%i:%s:%y:%z' "$DATAPULSE_PUBLICATION_STATE")" == "$marker_stat" ]]
  else
    [[ ! -e "$DATAPULSE_PUBLICATION_STATE" ]]
  fi
  printf 'PASS %s: remote reads=%s, starts=%s (expected %s), exit=0\n' \
    "$label" "$reads" "$starts" "$expected_starts"
}

run_case 'no marker' 0 0
[[ ! -s "$fixture/err" && ! -e "$DATAPULSE_PUBLISH_WAKE_STATE" ]]
printf 'pending-commit\nbuffered=1\n' > "$DATAPULSE_PUBLICATION_STATE"
cp "$DATAPULSE_PUBLICATION_STATE" "$fixture/marker-before"
marker_stat=$(stat -c '%i:%s:%y:%z' "$DATAPULSE_PUBLICATION_STATE")
mkdir -p "$(dirname -- "$DATAPULSE_PUBLISH_WAKE_STATE")"
printf '%s\n' "$REMOTE_HEAD" > "$DATAPULSE_PUBLISH_WAKE_STATE"
run_case 'unchanged remote head' 1 0
[[ ! -s "$fixture/err" ]]
export REMOTE_HEAD=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
run_case 'changed remote head' 1 1
[[ ! -s "$fixture/err" ]]
[[ "$(cat "$DATAPULSE_PUBLISH_WAKE_STATE")" == "$REMOTE_HEAD" ]]
run_case 'repeated remote head' 1 0
[[ ! -s "$fixture/err" ]]
cp "$DATAPULSE_PUBLISH_WAKE_STATE" "$fixture/state-before"
export REMOTE_STATUS=128
run_case 'failing remote call' 1 0
cmp "$fixture/state-before" "$DATAPULSE_PUBLISH_WAKE_STATE"
grep -F 'remote main read failed (exit 128)' "$fixture/err"
export REMOTE_STATUS=0
rm "$DATAPULSE_PUBLISH_WAKE_STATE"
run_case 'first observation' 1 1
[[ ! -s "$fixture/err" ]]
export REMOTE_HEAD=invalid
run_case 'invalid remote response' 1 0
grep -F 'invalid remote main response' "$fixture/err"
export REMOTE_HEAD=cccccccccccccccccccccccccccccccccccccccc START_STATUS=1
run_case 'failed start request' 1 1
grep -F 'publish start request failed' "$fixture/err"
run_case 'failed start is not retried for unchanged head' 1 0

# An installed copy must work with repository-relative default runtime paths.
mkdir -p "$fixture/installed"
cp "$script" "$fixture/installed/wake.sh"
export START_STATUS=0
script="$fixture/installed/wake.sh"
unset DATAPULSE_PUBLICATION_STATE DATAPULSE_PUBLISH_WAKE_STATE DATAPULSE_PUBLISH_UNIT
# Keep the assertion paths in the harness without exporting them to the script.
DATAPULSE_PUBLICATION_STATE="$DATAPULSE_REPO/var/log/publication-in-flight.sha"
DATAPULSE_PUBLISH_WAKE_STATE="$DATAPULSE_REPO/var/log/publish-wake-main.sha"
# The script must supply this default itself, so the stub is told what to expect.
export EXPECTED_UNIT=datapulse-health-publish.service
run_case 'installed copy with default runtime paths and unit' 1 1
[[ ! -s "$fixture/err" ]]
printf 'PASS marker bytes, inode, mtime and ctime unchanged; only PATH stubs used\n'
