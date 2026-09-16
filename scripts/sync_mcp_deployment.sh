#!/usr/bin/env bash
set -Eeuo pipefail

readonly DEFAULT_DEPLOYED_PATH=/home/redza/.local/share/datapulse-mcp/server.py
readonly DEFAULT_ENDPOINT=http://127.0.0.1:8788/mcp
readonly DEFAULT_SERVICE=datapulse-mcp.service
readonly DEFAULT_DROP_IN=/home/redza/.config/systemd/user/datapulse-mcp.service.d/99-source-marker.conf
readonly DEFAULT_PYTHONPATH=/home/redza/datapulse-my
# Sized against a measured production restart: the long-lived instance held
# the port closed for ~34s while draining, which the retired attempt-counted
# poll could never cover (see the readiness loop below).
readonly DEFAULT_READINESS_BUDGET_SECONDS=90
readonly ACCEPT='application/json, text/event-stream'

source_path=""
source_sha=""
source_date=""
deployed_path="${DATAPULSE_MCP_DEPLOYED_PATH:-$DEFAULT_DEPLOYED_PATH}"
endpoint="${DATAPULSE_MCP_ENDPOINT:-$DEFAULT_ENDPOINT}"
service="${DATAPULSE_MCP_SERVICE:-$DEFAULT_SERVICE}"
drop_in="${DATAPULSE_MCP_SOURCE_DROP_IN:-$DEFAULT_DROP_IN}"
pythonpath="${DATAPULSE_MCP_PYTHONPATH:-$DEFAULT_PYTHONPATH}"
readiness_budget_seconds="${DATAPULSE_MCP_READINESS_BUDGET_SECONDS:-$DEFAULT_READINESS_BUDGET_SECONDS}"
result_file=""
work_dir=""
source_tmp=""
drop_in_tmp=""
dry_run=false

log() {
  printf 'datapulse-mcp: %s\n' "$*"
}

write_result() {
  [[ -z "$result_file" ]] || printf '%s\n' "$1" > "$result_file"
}

fail() {
  write_result failed
  printf 'datapulse-mcp: ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  [[ -z "$source_tmp" || ! -e "$source_tmp" ]] || rm -f -- "$source_tmp"
  [[ -z "$drop_in_tmp" || ! -e "$drop_in_tmp" ]] || rm -f -- "$drop_in_tmp"
  [[ -z "$work_dir" || ! -d "$work_dir" ]] || rm -rf -- "$work_dir"
}

unexpected_error() {
  local rc=$?

  trap - ERR
  write_result failed
  printf 'datapulse-mcp: ERROR: unexpected failure (exit %s)\n' "$rc" >&2
  exit "$rc"
}
trap cleanup EXIT
trap unexpected_error ERR

# Read the SOURCE_COMMIT_SHA / SOURCE_COMMIT_DATE marker literals from a file.
# Prints "<sha>\n<date>"; exits non-zero when either marker is missing.
read_source_markers() {
  python3 - "$1" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
markers = {}
for name in ("DATAPULSE_MCP_SOURCE_SHA", "DATAPULSE_MCP_SOURCE_DATE"):
    match = re.search(r'os\.getenv\("%s",\s*"([^"]+)"\)' % name, text)
    if match is None:
        raise SystemExit("%s marker not found" % name)
    markers[name] = match.group(1)
print(markers["DATAPULSE_MCP_SOURCE_SHA"])
print(markers["DATAPULSE_MCP_SOURCE_DATE"])
PY
}

# Rewrite the two source-marker defaults in-place with the HEAD values.
# The deployed copy is the only file that ever carries the stamped values; the
# repository's mcp/server.py keeps its release-build literal untouched.
stamp_source_markers() {
  python3 - "$1" "$2" "$3" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
replacements = {
    "DATAPULSE_MCP_SOURCE_SHA": sys.argv[2],
    "DATAPULSE_MCP_SOURCE_DATE": sys.argv[3],
}
text = path.read_text(encoding="utf-8")
for name, value in replacements.items():
    text, count = re.subn(
        r'(os\.getenv\("%s",\s*")[^"]+(")' % name,
        lambda match, value=value: match.group(1) + value + match.group(2),
        text,
    )
    if count != 1:
        raise SystemExit("expected exactly one %s marker, found %d" % (name, count))
path.write_text(text, encoding="utf-8")
PY
}

# Emit the file with both marker defaults normalised to a fixed placeholder, so
# the copy-integrity digest compares every byte EXCEPT the stamped markers.
normalized_marker_body() {
  python3 - "$1" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
for name in ("DATAPULSE_MCP_SOURCE_SHA", "DATAPULSE_MCP_SOURCE_DATE"):
    text = re.sub(
        r'(os\.getenv\("%s",\s*")[^"]+(")' % name,
        lambda match: match.group(1) + "<normalised-marker>" + match.group(2),
        text,
        count=1,
    )
sys.stdout.write(text)
PY
}

normalized_marker_sha256() {
  normalized_marker_body "$1" | sha256sum | awk '{print $1}'
}

usage() {
  cat <<'EOF'
Usage: sync_mcp_deployment.sh --source PATH [options]

Options:
  --deployed-path PATH  Frozen deployed server.py path
  --endpoint URL        Local MCP endpoint used for post-restart verification
  --service NAME        systemd user service to restart
  --drop-in PATH        systemd drop-in that removes legacy source-marker overrides
  --result-file PATH    Write no-change, deployed, or failed for pipeline telemetry
  --source-sha SHA      Explicit advertised commit for callers outside a git
                        checkout (requires --source-date)
  --source-date DATE    Commit date (YYYY-MM-DD) paired with --source-sha
  --dry-run             Report planned actions without copying, restarting, or writing
EOF
}

while (( $# > 0 )); do
  case "$1" in
    --source)
      [[ $# -ge 2 ]] || fail '--source requires a path'
      source_path="$2"
      shift 2
      ;;
    --deployed-path)
      [[ $# -ge 2 ]] || fail '--deployed-path requires a path'
      deployed_path="$2"
      shift 2
      ;;
    --endpoint)
      [[ $# -ge 2 ]] || fail '--endpoint requires a URL'
      endpoint="$2"
      shift 2
      ;;
    --service)
      [[ $# -ge 2 ]] || fail '--service requires a name'
      service="$2"
      shift 2
      ;;
    --drop-in)
      [[ $# -ge 2 ]] || fail '--drop-in requires a path'
      drop_in="$2"
      shift 2
      ;;
    --result-file)
      [[ $# -ge 2 ]] || fail '--result-file requires a path'
      result_file="$2"
      shift 2
      ;;
    --source-sha)
      [[ $# -ge 2 ]] || fail '--source-sha requires a sha'
      source_sha="$2"
      shift 2
      ;;
    --source-date)
      [[ $# -ge 2 ]] || fail '--source-date requires a date'
      source_date="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "unknown argument: $1"
      ;;
  esac
done

[[ -n "$source_path" ]] || fail '--source is required'
[[ -f "$source_path" ]] || fail "source is not a regular file: $source_path"
[[ -f "$deployed_path" ]] || fail "deployed copy is not a regular file: $deployed_path"
[[ "$pythonpath" != *$'\n'* && "$pythonpath" != *$'\r'* && "$pythonpath" != *'"'* && "$pythonpath" != *"'"* ]] \
  || fail 'DATAPULSE_MCP_PYTHONPATH contains unsupported systemd Environment characters'
[[ "$readiness_budget_seconds" =~ ^[0-9]+$ ]] && (( readiness_budget_seconds >= 1 )) \
  || fail "DATAPULSE_MCP_READINESS_BUDGET_SECONDS must be a positive integer number of seconds, got: $readiness_budget_seconds"
command -v curl >/dev/null || fail 'curl is required'
command -v jq >/dev/null || fail 'jq is required'
command -v systemctl >/dev/null || fail 'systemctl is required'

uid="$(id -u)"
runtime_dir="/run/user/$uid"
[[ -d "$runtime_dir" ]] || fail "user runtime directory is missing: $runtime_dir"
export XDG_RUNTIME_DIR="$runtime_dir"

# The advertised commit is the repository HEAD of the source tree, never the
# release-build literal: the literal can go stale between releases, HEAD cannot.
# This is what makes the endpoint assertion a drift detector instead of a
# tautology over the copied file. Callers outside a checkout (CI driving a
# synthetic source tree) must supply the commit explicitly instead. Precedence
# is flag > HEAD > environment pair: a stray exported pair must never mask HEAD
# in a real checkout — the same authority rule the drop-in's UnsetEnvironment
# enforces for the service. When no input exists at all, fail naming the
# missing input; an empty sha is never an option.
head_sha=""
head_date=""
if [[ -n "$source_sha" ]]; then
  [[ -n "$source_date" ]] \
    || fail '--source-sha requires --source-date: the stamp writes both marker defaults'
  head_sha="$source_sha"
  head_date="$source_date"
  log "using explicit source sha=$head_sha date=$head_date from --source-sha/--source-date"
elif command -v git >/dev/null \
  && repo_root="$(git -C "$(dirname -- "$source_path")" rev-parse --show-toplevel 2>/dev/null)"; then
  head_sha="$(git -C "$repo_root" rev-parse HEAD)" \
    || fail "could not resolve repository HEAD in $repo_root"
  head_date="$(git -C "$repo_root" show -s --format=%cd --date=format:%Y-%m-%d HEAD)" \
    || fail "could not resolve repository HEAD date in $repo_root"
elif [[ -n "${DATAPULSE_MCP_SOURCE_SHA:-}" ]]; then
  [[ -n "${DATAPULSE_MCP_SOURCE_DATE:-}" ]] \
    || fail 'DATAPULSE_MCP_SOURCE_SHA is set without DATAPULSE_MCP_SOURCE_DATE: the stamp writes both marker defaults'
  head_sha="$DATAPULSE_MCP_SOURCE_SHA"
  head_date="$DATAPULSE_MCP_SOURCE_DATE"
  log "using source sha=$head_sha date=$head_date from DATAPULSE_MCP_SOURCE_SHA/DATAPULSE_MCP_SOURCE_DATE"
else
  fail "no source sha available: $source_path is not inside a git work tree and no override was given — pass --source-sha with --source-date, or set DATAPULSE_MCP_SOURCE_SHA and DATAPULSE_MCP_SOURCE_DATE"
fi
head_short_sha="${head_sha:0:7}"

source_sha256="$(sha256sum "$source_path" | awk '{print $1}')"
deployed_sha256="$(sha256sum "$deployed_path" | awk '{print $1}')"
normalized_source_sha256="$(normalized_marker_sha256 "$source_path")" \
  || fail "could not normalise $source_path for the copy-integrity digest"
# An unreadable or marker-less deployed copy must trigger a re-copy, not a crash.
normalized_deployed_sha256="$(normalized_marker_sha256 "$deployed_path" 2>/dev/null || printf 'unreadable')"

source_markers="$(read_source_markers "$source_path")" \
  || fail "could not read SOURCE_COMMIT_SHA/SOURCE_COMMIT_DATE markers from $source_path"
source_marker_sha="${source_markers%%$'\n'*}"
source_marker_date="${source_markers##*$'\n'}"
deployed_markers="$(read_source_markers "$deployed_path" 2>/dev/null || true)"
deployed_marker_sha="${deployed_markers%%$'\n'*}"
deployed_marker_date="${deployed_markers##*$'\n'}"

expected_fastmcp_version="$(python3 - "$source_path" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'FASTMCP_VERSION\s*=\s*["\']([^"\']+)["\']', text)
if match is None:
    raise SystemExit("FASTMCP_VERSION marker not found")
print(match.group(1))
PY
)" || fail "could not read FASTMCP_VERSION from $source_path"
expected_source_sha="$head_sha"
expected_source_version="v${expected_fastmcp_version}+${head_short_sha}"

if [[ "$source_marker_sha" != "$head_sha" ]]; then
  log "source marker literal $source_marker_sha is stale against HEAD $head_sha; deployed copy will be stamped from HEAD"
fi

readonly drop_in_content="[Service]
# The deployed file is authoritative; stale manual environment overrides must not
# mask the SOURCE_COMMIT_SHA/SOURCE_COMMIT_DATE embedded by release-build.
UnsetEnvironment=DATAPULSE_MCP_SOURCE_SHA DATAPULSE_MCP_SOURCE_DATE
Environment=PYTHONPATH=$pythonpath"

drop_in_changed=false
if [[ ! -f "$drop_in" ]] || [[ "$(<"$drop_in")" != "$drop_in_content" ]]; then
  drop_in_changed=true
fi

# Copy is needed when the files differ anywhere outside the two stamped marker
# lines; stamping is needed whenever the deployed markers are not exactly HEAD.
copy_needed=false
stamp_needed=false
[[ "$normalized_source_sha256" == "$normalized_deployed_sha256" ]] || copy_needed=true
[[ "$deployed_marker_sha" == "$head_sha" && "$deployed_marker_date" == "$head_date" ]] || stamp_needed=true

if [[ "$copy_needed" == false && "$stamp_needed" == false && "$drop_in_changed" == false ]]; then
  write_result no-change
  log "no change normalized_sha256=$normalized_source_sha256 raw_source_sha256=$source_sha256 raw_deployed_sha256=$deployed_sha256"
  log "deployed markers already at HEAD sha=$head_sha date=$head_date"
  exit 0
fi

if [[ "$dry_run" == true ]]; then
  log 'dry-run: no changes made'
  if [[ "$copy_needed" == true ]]; then
    log "dry-run: would copy $source_path (source_sha256=$source_sha256) to $deployed_path and stamp HEAD markers"
  else
    log "dry-run: deployed copy already matches source outside the markers (normalized_sha256=$normalized_source_sha256)"
  fi
  if [[ "$stamp_needed" == true ]]; then
    log "dry-run: would stamp deployed markers sha=$head_sha date=$head_date (currently sha=${deployed_marker_sha:-<missing>} date=${deployed_marker_date:-<missing>})"
  else
    log "dry-run: deployed markers already at HEAD"
  fi
  if [[ "$drop_in_changed" == true ]]; then
    log "dry-run: would install source-marker drop-in $drop_in"
  else
    log "dry-run: drop-in already current"
  fi
  log "dry-run: would restart $service and verify $endpoint reports $expected_source_version"
  exit 0
fi

timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
backup_path="${deployed_path}.${timestamp}.$$.bak"
drop_in_backup=""
cp -p -- "$deployed_path" "$backup_path" || fail "backup failed: $backup_path"
log "backup created $backup_path"

if [[ "$drop_in_changed" == true && -f "$drop_in" ]]; then
  drop_in_backup="${drop_in}.${timestamp}.$$.bak"
  cp -p -- "$drop_in" "$drop_in_backup" || fail "drop-in backup failed: $drop_in_backup"
  log "drop-in backup created $drop_in_backup"
fi

rollback() {
  local rollback_failed=false

  log 'rolling back failed deployment'
  cp -p -- "$backup_path" "$deployed_path" || rollback_failed=true
  if [[ -n "$drop_in_backup" ]]; then
    cp -p -- "$drop_in_backup" "$drop_in" || rollback_failed=true
  elif [[ "$drop_in_changed" == true ]]; then
    rm -f -- "$drop_in" || rollback_failed=true
  fi
  systemctl --user daemon-reload || rollback_failed=true
  systemctl --user restart "$service" || rollback_failed=true
  if [[ "$rollback_failed" == true ]]; then
    log 'ERROR: rollback was incomplete'
  else
    log 'rollback complete'
  fi
}

if [[ "$copy_needed" == true || "$stamp_needed" == true ]]; then
  source_tmp="$(mktemp "$(dirname "$deployed_path")/.server.py.sync.XXXXXX")"
  cp -- "$source_path" "$source_tmp" || fail 'copy to deployment temporary file failed'
  stamp_source_markers "$source_tmp" "$head_sha" "$head_date" \
    || fail "stamping deployed copy with HEAD sha=$head_sha date=$head_date failed"
  # Read the stamp back: the deployed file must advertise HEAD, provably.
  stamped_markers="$(read_source_markers "$source_tmp")" \
    || fail 'could not read back stamped markers from the deployment temporary file'
  stamped_marker_sha="${stamped_markers%%$'\n'*}"
  stamped_marker_date="${stamped_markers##*$'\n'}"
  [[ "$stamped_marker_sha" == "$head_sha" && "$stamped_marker_date" == "$head_date" ]] \
    || fail "stamped markers do not match HEAD: stamped_sha=$stamped_marker_sha stamped_date=$stamped_marker_date head_sha=$head_sha head_date=$head_date"
  # Copy integrity, honest about the stamp: normalise the two marker lines on
  # both sides and require every other byte to be identical. Both raw and
  # normalised digests are logged so a reader can see exactly what compared equal.
  normalized_tmp_sha256="$(normalized_marker_sha256 "$source_tmp")" \
    || fail 'could not normalise the deployment temporary file for the copy-integrity digest'
  [[ "$normalized_tmp_sha256" == "$normalized_source_sha256" ]] \
    || fail "copy integrity failed before install: normalized_source=$normalized_source_sha256 normalized_copy=$normalized_tmp_sha256"
  chmod --reference="$deployed_path" "$source_tmp" || fail 'preserving deployed mode failed'
  mv -f -- "$source_tmp" "$deployed_path" || fail "install failed: $deployed_path"
  source_tmp=""
  installed_sha256="$(sha256sum "$deployed_path" | awk '{print $1}')"
  installed_normalized_sha256="$(normalized_marker_sha256 "$deployed_path")" \
    || fail 'could not normalise the installed deployed file for the copy-integrity digest'
  [[ "$installed_normalized_sha256" == "$normalized_source_sha256" ]] \
    || fail "copy integrity failed after install: normalized_source=$normalized_source_sha256 normalized_deployed=$installed_normalized_sha256"
  log "copied source_sha256=$source_sha256 stamped_deployed_sha256=$installed_sha256 to $deployed_path"
  log "copy integrity normalized_source=$normalized_source_sha256 normalized_deployed=$installed_normalized_sha256"
  log "deployed markers stamped from HEAD sha=$head_sha date=$head_date"
else
  log "server copy unchanged normalized_sha256=$normalized_source_sha256 markers already at HEAD"
fi

if [[ "$drop_in_changed" == true ]]; then
  mkdir -p -- "$(dirname "$drop_in")"
  drop_in_tmp="$(mktemp "$(dirname "$drop_in")/.99-source-marker.conf.sync.XXXXXX")"
  printf '%s\n' "$drop_in_content" > "$drop_in_tmp"
  chmod 0644 "$drop_in_tmp"
  mv -f -- "$drop_in_tmp" "$drop_in"
  drop_in_tmp=""
  log "installed source-marker drop-in $drop_in"
  if ! systemctl --user daemon-reload; then
    rollback
    fail 'systemd user daemon-reload failed'
  fi
fi

if ! systemctl --user restart "$service"; then
  rollback
  fail "restart failed for $service"
fi
log "restarted $service via XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"

work_dir="$(mktemp -d /tmp/datapulse-mcp-sync.XXXXXX)"
initialize_payload='{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"datapulse-mcp-sync","version":"1"}},"id":1}'
# Readiness is a wall-clock deadline, not an attempt count: while the old
# process drains, nothing listens, so curl fails instantly with
# connection-refused instead of spending its 5s max-time. The previous
# 10-attempt loop therefore covered ~10s of drain, not the 60s its constants
# implied, and gave up on a restart measured to need ~34s — rolling back a
# deployment that was about to come up. The deadline makes the window what
# the number says it is, and the elapsed wait is logged on every exit path
# so the next resize starts from evidence instead of inference.
initialize_ok=false
readiness_started=$SECONDS
while (( SECONDS - readiness_started < readiness_budget_seconds )); do
  if curl -fsS --connect-timeout 2 --max-time 5 \
      -D "$work_dir/headers" -o "$work_dir/initialize" "$endpoint" \
      -H "Accept: $ACCEPT" -H 'Content-Type: application/json' \
      -d "$initialize_payload" 2> "$work_dir/curl-error"; then
    initialize_ok=true
    break
  fi
  sleep 1
done
readiness_wait=$(( SECONDS - readiness_started ))
log "initialize readiness wait=${readiness_wait}s budget=${readiness_budget_seconds}s endpoint=$endpoint"
if [[ "$initialize_ok" != true ]]; then
  rollback
  fail "local endpoint did not initialize after restart: $endpoint — waited ${readiness_wait}s of ${readiness_budget_seconds}s readiness budget (override: DATAPULSE_MCP_READINESS_BUDGET_SECONDS)"
fi

session_id="$(awk 'tolower($1)=="mcp-session-id:" {gsub("\r", "", $2); print $2}' "$work_dir/headers")"
if [[ -z "$session_id" ]]; then
  rollback
  fail 'initialize response omitted Mcp-Session-Id'
fi
awk '/^data: / {sub(/^data: /, ""); print; exit}' "$work_dir/initialize" > "$work_dir/initialize.json"
identity_surface=""
if identity_surface="$(jq -er \
    --arg sha "$expected_source_sha" \
    --arg source_version "$expected_source_version" \
    '(.result.serverInfo // {}) as $info
     | if $info.source_commit_sha == $sha and $info.version == $source_version
       then "legacy serverInfo.source_commit_sha"
       elif ($info.source_commit_sha == null or $info.source_commit_sha == "")
            and $info.version == $source_version
       then "FastMCP serverInfo.version source marker"
       else false
       end' \
    "$work_dir/initialize.json" 2>/dev/null)"; then
  :
else
  live_sha="$(jq -r '.result.serverInfo.source_commit_sha // "<missing>"' "$work_dir/initialize.json" 2>/dev/null || printf '<invalid>')"
  live_version="$(jq -r '.result.serverInfo.version // "<missing>"' "$work_dir/initialize.json" 2>/dev/null || printf '<invalid>')"
  live_short_sha="$live_sha"
  [[ "$live_short_sha" != "<missing>" ]] || live_short_sha="${live_version##*+}"
  live_short_sha="${live_short_sha:0:7}"
  rollback
  fail "live identity mismatch: served_short_sha=$live_short_sha does not match head_short_sha=$head_short_sha served_version=$live_version served_sha=$live_sha expected_version=$expected_source_version head_sha=$head_sha — the endpoint is not reporting the repository HEAD source marker"
fi

if ! curl -fsS --connect-timeout 2 --max-time 5 "$endpoint" \
    -H "Accept: $ACCEPT" -H 'Content-Type: application/json' \
    -H "Mcp-Session-Id: $session_id" \
    -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
    >/dev/null 2> "$work_dir/curl-error"; then
  rollback
  fail 'MCP initialized notification failed'
fi
if ! curl -fsS --connect-timeout 2 --max-time 5 "$endpoint" \
    -H "Accept: $ACCEPT" -H 'Content-Type: application/json' \
    -H "Mcp-Session-Id: $session_id" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":2}' \
    > "$work_dir/tools" 2> "$work_dir/curl-error"; then
  rollback
  fail 'MCP tools/list verification failed'
fi
awk '/^data: / {sub(/^data: /, ""); print; exit}' "$work_dir/tools" > "$work_dir/tools.json"
if ! jq -e '
    (.result.tools | type == "array" and length > 0)
    and all(.result.tools[];
      .annotations.readOnlyHint == true
      and .annotations.destructiveHint == false
      and .annotations.idempotentHint == true
      and .annotations.openWorldHint == true)
  ' "$work_dir/tools.json" >/dev/null; then
  rollback
  fail 'live tools/list is missing the complete read-only annotations'
fi

tool_count="$(jq -r '.result.tools | length' "$work_dir/tools.json")"
write_result deployed
log "verified endpoint=$endpoint source_commit_sha=$expected_source_sha head_short_sha=$head_short_sha tools=$tool_count annotations=complete"
log "identity surface=$identity_surface expected_version=$expected_source_version"
log 'deployment complete'
