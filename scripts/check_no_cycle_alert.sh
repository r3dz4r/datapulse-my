#!/usr/bin/env bash
set -euo pipefail

usage() { printf 'Usage: %s [--history PATH] [--threshold-minutes N] [--alert PATH] [--now ISO8601]\n' "$0" >&2; }
history="${DATAPULSE_HISTORY_FILE:-health/history.jsonl}"
threshold="${DATAPULSE_CYCLE_SLA_MINUTES:-$(( ${DATAPULSE_CADENCE_MINUTES:-5} * 3 ))}"
alert="${DATAPULSE_ALERT_FILE:-var/log/heartbeat-FAIL}"
now="${DATAPULSE_NOW:-}"
while (($#)); do
  case "$1" in
    --history) history="$2"; shift 2 ;;
    --threshold-minutes) threshold="$2"; shift 2 ;;
    --alert) alert="$2"; shift 2 ;;
    --now) now="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done
[[ "$threshold" =~ ^[1-9][0-9]*$ ]] || { printf 'Invalid threshold: %s\n' "$threshold" >&2; exit 2; }
[[ -n "$now" ]] || now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if python3 - "$history" "$threshold" "$now" <<'PY'
import json, sys
from datetime import datetime
path, threshold, now = sys.argv[1], int(sys.argv[2]), sys.argv[3]
cutoff = datetime.fromisoformat(now.replace("Z", "+00:00")).timestamp() - threshold * 60
try:
    lines = open(path, encoding="utf-8")
except OSError:
    raise SystemExit(1)
for line in lines:
    try:
        row = json.loads(line)
        observed = row.get("observed_at") or row.get("timestamp")
        successful = row.get("probe_outcome") == "success" or row.get("status") == "SUCCESSFUL"
        if successful and observed and datetime.fromisoformat(observed.replace("Z", "+00:00")).timestamp() >= cutoff:
            raise SystemExit(0)
    except (ValueError, TypeError, json.JSONDecodeError):
        continue
raise SystemExit(1)
PY
then
  rm -f "$alert"
  exit 0
fi
mkdir -p "$(dirname "$alert")"
printf 'ALERT no successful DataPulse cycle within %s minutes (history=%s, now=%s)\n' "$threshold" "$history" "$now" | tee "$alert" >&2
exit 1
