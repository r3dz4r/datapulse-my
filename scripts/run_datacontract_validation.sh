#!/usr/bin/env bash
# Excluded unprobed rows are still validated against health.schema.json by
# scripts/gen_quality_profile.py and scripts/validate_at_runtime.py.
set -Eeuo pipefail

prepare_health_snapshot() {
  python3 - "$1" "$2" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


# health.schema.json permits null only for explicitly unprobed onboarding rows.
def is_explicitly_unprobed(row: dict[str, object]) -> bool:
    return (
        "last_checked" in row
        and row["last_checked"] is None
        and row.get("status") == "unknown-freshness"
    )


snapshot = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
retained = []
excluded = []
for row in snapshot["datasets"]:
    if is_explicitly_unprobed(row):
        excluded.append(row["dataset_id"])
    else:
        retained.append(row)
snapshot["datasets"] = retained
Path(sys.argv[2]).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"DataPulse contract validation: excluded explicitly unprobed count={len(excluded)} dataset_ids={json.dumps(sorted(excluded))}")
PY
}

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
contract="$root_dir/datacontract/datapulse.contract.yaml"
health_path="${DATAPULSE_HEALTH_PATH:-$root_dir/health/latest.json}"
manifest_path="${DATAPULSE_MANIFEST_PATH:-$root_dir/datapulse.json}"

if ! command -v datacontract >/dev/null 2>&1; then
  printf '%s\n' 'datacontract-cli is required; install the pinned CI dependency with: python3 -m pip install "datacontract-cli[duckdb]==0.12.5"' >&2
  exit 127
fi

for path in "$contract" "$health_path" "$manifest_path"; do
  [[ -f "$path" ]] || { printf 'Required contract input is missing: %s\n' "$path" >&2; exit 1; }
done

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
prepare_health_snapshot "$health_path" "$work_dir/health_snapshot.json"
cp "$manifest_path" "$work_dir/datapulse_manifest.json"
resolved_contract="$work_dir/datapulse.contract.yaml"
sed "s|\${DATAPULSE_CONTRACT_DATA_DIR}|$work_dir|g" "$contract" > "$resolved_contract"

printf 'DataPulse contract validation: health=%s manifest=%s\n' "$health_path" "$manifest_path"
if datacontract test "$resolved_contract" --checks schema,quality; then
  printf '%s\n' 'DataPulse contract validation: OK'
else
  status=$?
  printf '%s\n' 'DataPulse contract validation: FAILED; canonical health or manifest contract drift detected.' >&2
  exit "$status"
fi
