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
  "schema": "datapulse/v0.4/dataset-health",
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

mkdir "$fixture_dir/bin" "$fixture_dir/full"
cat > "$fixture_dir/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
output_path=""
headers_path=""
while (( $# > 0 )); do
  case "$1" in
    --output)
      output_path="$2"
      shift 2
      ;;
    --dump-header)
      headers_path="$2"
      shift 2
      ;;
    --max-time|--write-out)
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
[[ -z "$output_path" || "$output_path" == "/dev/null" ]] \
  || printf '[{"id":1,"name":"alpha"}]\n' > "$output_path"
[[ -z "$headers_path" ]] \
  || printf 'HTTP/1.1 200 OK\r\nLast-Modified: Sat, 08 Aug 2026 12:00:00 GMT\r\n\r\n' > "$headers_path"
printf '200'
SH
chmod +x "$fixture_dir/bin/curl"
cat > "$fixture_dir/full/manifest.json" <<'JSON'
{
  "datasets": [
    {
      "id": "captured-json",
      "url": "https://example.invalid/captured.json",
      "refresh_frequency": "daily",
      "namespace": "test"
    }
  ]
}
JSON
(
  cd "$fixture_dir/full"
  PATH="$fixture_dir/bin:$PATH" bash "$repo_root/scripts/check.sh" manifest.json
) > "$fixture_dir/full-output.json"
jq -e '
  (.datasets | length) == 1
  and (.datasets[0].first_row_hash | startswith("shape-v1:"))
  and .datasets[0].content_shape_changed == false
' "$fixture_dir/full-output.json" >/dev/null

mkdir "$fixture_dir/full-comparison"
cp "$fixture_dir/full/manifest.json" "$fixture_dir/full-comparison/manifest.json"
(
  cd "$fixture_dir/full-comparison"
  PATH="$fixture_dir/bin:$PATH" bash "$repo_root/scripts/check.sh" \
    --compare-health manifest.json
) > "$fixture_dir/full-comparison-output.json" \
  2> "$fixture_dir/full-comparison-report.json"
jq -e '.datasets_compared == 1 and (.differences | length) == 1' \
  "$fixture_dir/full-comparison-report.json" >/dev/null

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
