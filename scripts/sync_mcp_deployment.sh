#!/usr/bin/env bash
set -Eeuo pipefail

readonly DEFAULT_DEPLOYED_PATH=/home/redza/.local/share/datapulse-mcp/server.py
readonly DEFAULT_ENDPOINT=http://127.0.0.1:8788/mcp
readonly DEFAULT_SERVICE=datapulse-mcp.service
readonly DEFAULT_DROP_IN=/home/redza/.config/systemd/user/datapulse-mcp.service.d/99-source-marker.conf
readonly ACCEPT='application/json, text/event-stream'

source_path=""
deployed_path="${DATAPULSE_MCP_DEPLOYED_PATH:-$DEFAULT_DEPLOYED_PATH}"
endpoint="${DATAPULSE_MCP_ENDPOINT:-$DEFAULT_ENDPOINT}"
service="${DATAPULSE_MCP_SERVICE:-$DEFAULT_SERVICE}"
drop_in="${DATAPULSE_MCP_SOURCE_DROP_IN:-$DEFAULT_DROP_IN}"
result_file=""
work_dir=""
source_tmp=""
drop_in_tmp=""

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

usage() {
  cat <<'EOF'
Usage: sync_mcp_deployment.sh --source PATH [options]

Options:
  --deployed-path PATH  Frozen deployed server.py path
  --endpoint URL        Local MCP endpoint used for post-restart verification
  --service NAME        systemd user service to restart
  --drop-in PATH        systemd drop-in that removes legacy source-marker overrides
  --result-file PATH    Write no-change, deployed, or failed for pipeline telemetry
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
command -v curl >/dev/null || fail 'curl is required'
command -v jq >/dev/null || fail 'jq is required'
command -v systemctl >/dev/null || fail 'systemctl is required'

uid="$(id -u)"
runtime_dir="/run/user/$uid"
[[ -d "$runtime_dir" ]] || fail "user runtime directory is missing: $runtime_dir"
export XDG_RUNTIME_DIR="$runtime_dir"

source_sha256="$(sha256sum "$source_path" | awk '{print $1}')"
deployed_sha256="$(sha256sum "$deployed_path" | awk '{print $1}')"
expected_source_sha="$(python3 - "$source_path" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(
    r'SOURCE_COMMIT_SHA\s*=\s*os\.getenv\("DATAPULSE_MCP_SOURCE_SHA",\s*"([^"]+)"\)',
    text,
)
if match is None:
    raise SystemExit("SOURCE_COMMIT_SHA marker not found")
print(match.group(1))
PY
)" || fail "could not read SOURCE_COMMIT_SHA from $source_path"
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
expected_source_version="v${expected_fastmcp_version}+${expected_source_sha:0:7}"

readonly drop_in_content='[Service]
# The deployed file is authoritative; stale manual environment overrides must not
# mask the SOURCE_COMMIT_SHA/SOURCE_COMMIT_DATE embedded by release-build.
UnsetEnvironment=DATAPULSE_MCP_SOURCE_SHA DATAPULSE_MCP_SOURCE_DATE'

drop_in_changed=false
if [[ ! -f "$drop_in" ]] || [[ "$(<"$drop_in")" != "$drop_in_content" ]]; then
  drop_in_changed=true
fi

if [[ "$source_sha256" == "$deployed_sha256" && "$drop_in_changed" == false ]]; then
  write_result no-change
  log "no change source_sha256=$source_sha256"
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

if [[ "$source_sha256" != "$deployed_sha256" ]]; then
  source_tmp="$(mktemp "$(dirname "$deployed_path")/.server.py.sync.XXXXXX")"
  cp -- "$source_path" "$source_tmp" || fail 'copy to deployment temporary file failed'
  chmod --reference="$deployed_path" "$source_tmp" || fail 'preserving deployed mode failed'
  mv -f -- "$source_tmp" "$deployed_path" || fail "install failed: $deployed_path"
  source_tmp=""
  log "copied source_sha256=$source_sha256 to $deployed_path"
else
  log "server copy unchanged source_sha256=$source_sha256"
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
initialize_ok=false
for (( attempt=1; attempt<=10; attempt++ )); do
  if curl -fsS --connect-timeout 2 --max-time 5 \
      -D "$work_dir/headers" -o "$work_dir/initialize" "$endpoint" \
      -H "Accept: $ACCEPT" -H 'Content-Type: application/json' \
      -d "$initialize_payload" 2> "$work_dir/curl-error"; then
    initialize_ok=true
    break
  fi
  sleep 1
done
if [[ "$initialize_ok" != true ]]; then
  rollback
  fail "local endpoint did not initialize after restart: $endpoint"
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
  rollback
  fail "live identity mismatch: checked=legacy serverInfo.source_commit_sha or FastMCP serverInfo.version expected_version=$expected_source_version expected_sha=$expected_source_sha live_version=$live_version live_sha=$live_sha"
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
log "verified endpoint=$endpoint source_commit_sha=$expected_source_sha tools=$tool_count annotations=complete"
log "identity surface=$identity_surface expected_version=$expected_source_version"
log 'deployment complete'
