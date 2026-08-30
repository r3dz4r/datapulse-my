#!/usr/bin/env bash
set -Eeuo pipefail

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
cp "$health_path" "$work_dir/health_snapshot.json"
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
