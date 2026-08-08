#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture_dir="$(mktemp -d)"
trap 'rm -rf "$fixture_dir"' EXIT

cat > "$fixture_dir/manifest.json" <<'JSON'
{
  "datasets": [
    {
      "id": "captured-daily",
      "url": "https://example.invalid/captured.json",
      "refresh_frequency": "daily",
      "namespace": "test"
    }
  ]
}
JSON

cat > "$fixture_dir/health.json" <<'JSON'
{
  "schema": "datapulse/v0.3/dataset-health",
  "checked_at": "2099-01-01T00:00:00Z",
  "_trust_summary": {"datasets_total": 1},
  "datasets": [
    {
      "dataset_id": "captured-daily",
      "last_checked": "2099-01-01T00:00:00Z",
      "status": "fresh",
      "http_status": 200,
      "last_modified": "2098-12-31T12:00:00Z",
      "freshness_signal_source": "last_modified_header",
      "record_count": 1
    }
  ]
}
JSON

mkdir "$fixture_dir/default" "$fixture_dir/comparison"
cp "$fixture_dir/manifest.json" "$fixture_dir/default/manifest.json"
cp "$fixture_dir/health.json" "$fixture_dir/default/latest.json"
cp "$fixture_dir/manifest.json" "$fixture_dir/comparison/manifest.json"
cp "$fixture_dir/health.json" "$fixture_dir/comparison/latest.json"
mv "$fixture_dir/default/latest.json" "$fixture_dir/default/health.json"
mv "$fixture_dir/comparison/latest.json" "$fixture_dir/comparison/health.json"
mkdir "$fixture_dir/default/health" "$fixture_dir/comparison/health"
mv "$fixture_dir/default/health.json" "$fixture_dir/default/health/latest.json"
mv "$fixture_dir/comparison/health.json" "$fixture_dir/comparison/health/latest.json"

status_before="$(git -C "$repo_root" status --short)"
(
  cd "$fixture_dir/default"
  bash "$repo_root/scripts/check.sh" --due --tier daily manifest.json
) > "$fixture_dir/default-output.json"
cmp "$fixture_dir/health.json" "$fixture_dir/default-output.json"

(
  cd "$fixture_dir/comparison"
  bash "$repo_root/scripts/check.sh" --compare-health --due --tier daily manifest.json
) > "$fixture_dir/comparison-output.json" 2> "$fixture_dir/comparison-report.json"
cmp "$fixture_dir/health.json" "$fixture_dir/comparison-output.json"
jq -e '
  .datasets_compared == 1
  and .differences[0].dataset_id == "captured-daily"
  and .differences[0].fields.status_reason.new == "freshness-within-window"
' "$fixture_dir/comparison-report.json" >/dev/null

cat > "$fixture_dir/bad-manifest.json" <<'JSON'
{"datasets":[{"id":"captured-daily","refresh_frequency":"fortnightly"}]}
JSON
if python3 "$repo_root/scripts/compare_health.py" \
  "$fixture_dir/health.json" "$fixture_dir/bad-manifest.json" \
  > /dev/null 2> "$fixture_dir/failure.txt"; then
  printf 'Expected internal classifier failure\n' >&2
  exit 1
fi
rg -q 'Health comparison failed.*unsupported refresh_frequency' "$fixture_dir/failure.txt"

status_after="$(git -C "$repo_root" status --short)"
[[ "$status_before" == "$status_after" ]]
printf 'check.sh comparison mode passed\n'
