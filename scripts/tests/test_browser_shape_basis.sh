#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture_dir="$(mktemp -d)"
trap 'rm -rf "$fixture_dir"' EXIT

mkdir "$fixture_dir/bin" "$fixture_dir/success" "$fixture_dir/no-page"

cat > "$fixture_dir/policy.json" <<'JSON'
{
  "version": 1,
  "defaults": {"adapter": "direct"},
  "datasets": {
    "browser-fixture": {
      "adapter": "browser",
      "browser": {"date-pattern": "2026-09-01", "wait-seconds": 0}
    }
  }
}
JSON

cat > "$fixture_dir/manifest.json" <<'JSON'
{"datasets":[{"id":"browser-fixture","url":"https://example.invalid/page","refresh_frequency":"daily","namespace":"test"}]}
JSON

cat > "$fixture_dir/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

url=""
for argument in "$@"; do
  if [[ "$argument" == http://* || "$argument" == https://* ]]; then
    url="$argument"
  fi
done
if [[ "$url" == */robots.txt ]]; then
  exit 0
fi
if [[ "$url" == */tabs/open ]]; then
  if [[ "${CAMOFOX_FIXTURE_MODE:-success}" == "no-page" ]]; then
    printf '{}'
  else
    printf '{"tabId":"fixture-tab"}'
  fi
elif [[ "$url" == */tabs/fixture-tab/snapshot\?* ]]; then
  printf '{"snapshot":"row \\"1 A\\" 2026-09-01 %s"}' \
    'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
elif [[ "$url" == */tabs/fixture-tab ]]; then
  :
else
  printf '200'
fi
SH
chmod +x "$fixture_dir/bin/curl"

cat > "$fixture_dir/bin/sleep" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod +x "$fixture_dir/bin/sleep"

run_check() {
  local destination="$1"
  local mode="${2:-success}"
  cp "$fixture_dir/manifest.json" "$destination/manifest.json"
  (
    cd "$destination"
    PATH="$fixture_dir/bin:$PATH" \
      DATAPULSE_PROBE_POLICY="$fixture_dir/policy.json" \
      CAMOFOX_FIXTURE_MODE="$mode" CAMOFOX_TIMEOUT=1 \
      bash "$repo_root/scripts/check.sh" manifest.json
  )
}

run_check "$fixture_dir/success" > "$fixture_dir/success/output.json"
jq -e \
  '.datasets[0].status == "browser-dependent" and
   .datasets[0].message == "Browser check succeeded" and
   .datasets[0].shape_basis == "untyped" and
   .datasets[0].first_row_hash == null' \
  "$fixture_dir/success/output.json" >/dev/null || {
    jq . "$fixture_dir/success/output.json" >&2
    exit 1
  }

run_check "$fixture_dir/no-page" no-page > "$fixture_dir/no-page/output.json"
jq -e \
  '.datasets[0].status == "browser-dependent" and
   .datasets[0].message == "Camofox returned no tab id" and
   .datasets[0].shape_basis == null and
   .datasets[0].first_row_hash == null' \
  "$fixture_dir/no-page/output.json" >/dev/null || {
    jq . "$fixture_dir/no-page/output.json" >&2
    exit 1
  }
