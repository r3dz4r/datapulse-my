#!/usr/bin/env bash
# Verify one assembled Pages artifact at an explicit HTTPS origin.  This is used
# for both the isolated preview promotion gate and the post-production readback.
set -Eeuo pipefail

usage() {
  echo "usage: $0 --base-url URL --site DIR --sigstore-signed true|false --health-only true|false --sigstore-publication DIR --source-commit SHA [--cosign PATH]" >&2
  exit 64
}

base_url="${DATAPULSE_SERVED_BASE_URL:-}"
site_dir="${DATAPULSE_SITE_DIR:-_site}"
sigstore_signed="${DATAPULSE_SIGSTORE_SIGNED:-}"
health_only="${DATAPULSE_HEALTH_ONLY:-}"
publication_dir="${DATAPULSE_SIGSTORE_PUBLICATION_DIR:-}"
source_commit="${DATAPULSE_SOURCE_COMMIT:-${GITHUB_SHA:-}}"
cosign_bin="${DATAPULSE_COSIGN:-}"
while (($#)); do
  case "$1" in
    --base-url) base_url="$2"; shift 2 ;;
    --site) site_dir="$2"; shift 2 ;;
    --sigstore-signed) sigstore_signed="$2"; shift 2 ;;
    --health-only) health_only="$2"; shift 2 ;;
    --sigstore-publication) publication_dir="$2"; shift 2 ;;
    --source-commit) source_commit="$2"; shift 2 ;;
    --cosign) cosign_bin="$2"; shift 2 ;;
    *) usage ;;
  esac
done
fail() { echo "::error title=Cloudflare Pages contract failed::$1"; exit 1; }
[[ "$base_url" =~ ^https://[^/:[:space:]]+(:[0-9]+)?$ ]] || fail "invalid served base URL"
[[ -d "$site_dir" && -s "$site_dir/health/latest.json" ]] || fail "assembled site is missing health/latest.json"
[[ "$sigstore_signed" == true || "$sigstore_signed" == false ]] || fail "invalid Sigstore signing result"
[[ "$health_only" == true || "$health_only" == false ]] || fail "invalid health-only mode"
[[ -n "$publication_dir" && -n "$source_commit" ]] || fail "missing staged signing inputs"
smoke_dir="$(mktemp -d)"
trap 'rm -rf "$smoke_dir"' EXIT
fetch() {
  local surface="$1" url="$2" output="$3"
  [[ "$url" =~ ^https://[^[:space:]]+$ ]] || fail "invalid URL for $surface"
  mkdir -p "$(dirname "$output")"
  curl --fail --location --silent --show-error --proto '=https' --retry 3 --retry-delay 5 --retry-all-errors --connect-timeout 10 --max-time 30 "$url" --output "$output" || fail "missing or stale served surface: $surface"
}
fetch_alias() {
  local surface="$1" url="$2" requested_path headers body resolved_headers resolved_body location status
  requested_path="${url#"$base_url"}"; headers="$smoke_dir/${surface// /-}.headers"; body="$smoke_dir/${surface// /-}.body"; resolved_headers="$smoke_dir/${surface// /-}.resolved.headers"; resolved_body="$smoke_dir/${surface// /-}.resolved.body"
  [[ "$url" =~ ^https://[^[:space:]]+$ ]] || fail "invalid URL for $surface"
  status="$(curl --fail --silent --show-error --proto '=https' --retry 3 --retry-delay 5 --retry-all-errors --connect-timeout 10 --max-time 30 --dump-header "$headers" --output "$body" --write-out '%{http_code}' "$url")" || fail "could not fetch compatibility alias: $surface"
  location="$(awk 'tolower($1) == "location:" { sub(/[\r ]+$/, "", $2); print $2; exit }' "$headers")"; [[ "$location" == "${location%#}" ]] || location="${location%#}"
  if [[ -n "$location" ]]; then
    [[ "$requested_path" == /landing.html && "$status" == 308 ]] || fail "$surface uses an unexpected edge redirect to ${location}"
    [[ "$location" == /landing || "$location" == "$base_url/landing" ]] || fail "$surface normalizes to an unexpected location: ${location}"
    status="$(curl --fail --silent --show-error --proto '=https' --retry 3 --retry-delay 5 --retry-all-errors --connect-timeout 10 --max-time 30 --dump-header "$resolved_headers" --output "$resolved_body" --write-out '%{http_code}' "$base_url/landing")" || fail "could not fetch normalized compatibility alias: $surface"
    [[ "$status" == 200 ]] || fail "$surface normalized alias returned HTTP $status"
    location="$(awk 'tolower($1) == "location:" { sub(/[\r ]+$/, "", $2); print $2; exit }' "$resolved_headers")"; [[ -z "$location" ]] || fail "$surface normalized alias redirects again to ${location}"; body="$resolved_body"
  else [[ "$status" == 200 ]] || fail "$surface returned unexpected HTTP $status"; fi
  grep -Fq '<title>DataPulse dataset register</title>' "$body" || fail "$surface lacks alias document identity"
  grep -Fq '<link rel="canonical" href="/">' "$body" || fail "$surface lacks root canonical identity"
  grep -Fq 'http-equiv="refresh" content="0; url=/"' "$body" || fail "$surface lacks root browser fallback"
  grep -Fq 'href="/">DataPulse dataset register</a>' "$body" || fail "$surface lacks accessible root fallback"
}
# Permit Pages propagation at either origin before comparing exact served bytes.
sleep 30
expected_dataset_count="$(jq -er '.datasets | select(type == "array" and length > 0) | length' "$site_dir/datapulse.json")" || fail "assembled manifest has no dataset array"
fetch "dataset register" "$base_url/" "$smoke_dir/index.html"
grep -q '<title>DataPulse Dataset Register</title>' "$smoke_dir/index.html" || fail "origin root is not the DataPulse dataset register"
grep -q '__DATAPULSE_DATA__' "$smoke_dir/index.html" || fail "origin root has no embedded register health payload"
observed_register_rows="$(grep -o '<article class="register-row' "$smoke_dir/index.html" | wc -l)"; [[ "$observed_register_rows" -eq "$expected_dataset_count" ]] || fail "origin root register rows mismatch: expected $expected_dataset_count, observed $observed_register_rows"
grep -q 'DataPulse MY' "$smoke_dir/index.html" && fail "origin root retains the retired product-name alias"
fetch_alias landing.html "$base_url/landing.html"; fetch_alias landing "$base_url/landing"; fetch_alias dashboard "$base_url/dashboard"
fetch "health snapshot" "$base_url/health/latest.json" "$smoke_dir/health/latest.json"; cmp -s "$site_dir/health/latest.json" "$smoke_dir/health/latest.json" || fail "served canonical health differs from the deployed bytes"
sigstore_path="signatures/health.latest.sigstore.json"
if [[ "$sigstore_signed" == true ]]; then
  staged_bundle="$publication_dir/health.latest.sigstore.json"; staged_manifest="$publication_dir/datapulse.json"; test -s "$staged_bundle" || fail "verified Sigstore bundle is missing from the deploy job"; test -s "$staged_manifest" || fail "signed manifest snapshot is missing from the deploy job"
  fetch "Sigstore health DSSE bundle" "$base_url/$sigstore_path" "$smoke_dir/health.latest.sigstore.json"; cmp -s "$staged_bundle" "$smoke_dir/health.latest.sigstore.json" || fail "served Sigstore bundle differs from the verified staged artifact"
  fetch "signed manifest snapshot" "$base_url/signatures/datapulse.json" "$smoke_dir/signatures/datapulse.json"; cmp -s "$staged_manifest" "$smoke_dir/signatures/datapulse.json" || fail "served signed manifest snapshot differs from the verified staged artifact"
  [[ -n "$cosign_bin" && -x "$cosign_bin" ]] || fail "Cosign verifier is required for a signed bundle"
  python3 scripts/verify_sigstore_bundle.py --health "$site_dir/health/latest.json" --manifest "$smoke_dir/signatures/datapulse.json" --legacy-chain-head "$publication_dir/chain_head.json" --source-commit "$source_commit" --bundle "$smoke_dir/health.latest.sigstore.json" --certificate-identity "https://github.com/r3dz4r/datapulse-my/.github/workflows/deploy-cloudflare-pages.yml@refs/heads/main" --certificate-oidc-issuer "https://token.actions.githubusercontent.com" --cosign "$cosign_bin" || fail "served Sigstore bundle verification failed"
else
  status="$(curl --location --silent --show-error --proto '=https' --retry 3 --retry-delay 5 --retry-all-errors --connect-timeout 10 --max-time 30 --output "$smoke_dir/unsigned-sigstore-response" --write-out '%{http_code}' "$base_url/$sigstore_path")" || fail "could not prove optional Sigstore bundle absence"
  if [[ "$status" == 200 ]]; then grep -q 'application/vnd.dev.sigstore.bundle' "$smoke_dir/unsigned-sigstore-response" && fail "stale Sigstore bundle is still served after signing became unavailable (HTTP $status)"; grep -Eq '<html[ >]|<head>|id="main-content"|hero-heading' "$smoke_dir/unsigned-sigstore-response" || fail "stale Sigstore bundle is still served after signing became unavailable (HTTP $status)"; elif [[ "$status" != 404 ]]; then fail "unexpected HTTP status while proving optional Sigstore bundle absence (HTTP $status)"; fi
fi
if [[ "$health_only" == true ]]; then staged_proof="$RUNNER_TEMP/preserved-release-proof/release-verification.md"; else staged_proof="docs/release-verification.md"; fi
test -s "$staged_proof" || fail "staged release proof is missing"; fetch "release reproducibility proof" "$base_url/release-verification.md" "$smoke_dir/release-verification.md"; cmp -s "$staged_proof" "$smoke_dir/release-verification.md" || fail "served release proof differs from staged artifact"
python3 - "$smoke_dir/release-verification.md" "$source_commit" "$smoke_dir/health/latest.json" mcp.json "$health_only" <<'PY'
import json,re,sys
from pathlib import Path
proof, sha, health_path, mcp_path, health_only=sys.argv[1:]; contents=Path(proof).read_text(encoding='utf-8')
if health_only == 'true':
 required={'release-proof title':r'^# Release reproducibility verification$','verification timestamp':r'^- (?:Generated|Verified) at: `[^`\\n]+`$','Source SHA':r'^- Source SHA: `[0-9a-f]{7,64}`$','Profile result':r'^- Profile result: .+$','Total files built':r'^- Total files built: .+$','hash table':r'^\\| Path category \\| File count \\| First-run hash \\| Second-run hash \\| Match\\? \\|$','hash table category row':r'^\\| (?![-: ]+\\|)[^|]+ \\| \\d+ \\|','Reproduction section':r'^## Reproduction$'}; missing=[k for k,v in required.items() if not re.search(v,contents,re.M)]
else:
 health=json.loads(Path(health_path).read_text()); tools=json.loads(Path(mcp_path).read_text())['tools']; required=('<!-- generated: scripts/verify_release_reproducible.py; do not hand-edit -->','- Status: `current generated release proof`',f'- Source SHA: `{sha}`',f"- Health checked at: `{health['checked_at']}`",f"- Dataset count: `{len(health['datasets'])}`",f'- MCP tool count: `{len(tools)}`','- Protocol result: `byte-identical isolated release-build runs`'); missing=[v for v in required if v not in contents]
if missing: raise SystemExit('release proof drift: '+'; '.join(missing))
PY
mapfile -t pages < <(jq -er '.pages[]' config/public-surfaces.json); mapfile -t artifacts < <(jq -er '.artifacts[]' config/public-surfaces.json)
for path in "${pages[@]}" "${artifacts[@]}"; do [[ "$path" == / || "$path" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail "unsafe declared public path: $path"; if [[ "$path" == */ ]]; then declared_file="$(find "$site_dir${path}" -type f -print -quit)" || fail "declared collection is missing: $path"; [[ -n "$declared_file" ]] || fail "declared collection is empty: $path"; path="/${declared_file#"$site_dir/"}"; fi; fetch "declared public surface $path" "$base_url$path" "$smoke_dir/surfaces${path%/}/index"; done
python3 - "$smoke_dir/index.html" "$smoke_dir/health/latest.json" <<'PY'
import json,re,sys
from pathlib import Path
dashboard=Path(sys.argv[1]).read_text(); health=json.loads(Path(sys.argv[2]).read_text()); match=re.search(r'window\.__DATAPULSE_DATA__\s*=\s*\{health:\s*',dashboard)
if match is None: raise SystemExit('dashboard has no embedded health payload')
embedded,_=json.JSONDecoder().raw_decode(dashboard[match.end():])
if embedded['checked_at'] != health['checked_at']: raise SystemExit('embedded dashboard checked_at differs from served health/latest.json')
if len(embedded['datasets']) != len(health['datasets']): raise SystemExit('embedded dashboard dataset count differs from served health/latest.json')
if dashboard.count('"health_report":') != len(health['datasets']): raise SystemExit('dashboard dataset-card count differs from served health/latest.json')
PY
expected_dataset_count="$(jq -er '.datasets | select(type == "array" and length > 0) | length' "$smoke_dir/health/latest.json")" || fail "served health has no dataset array"
for kind in trends drift reconciliation; do fetch "$kind snapshot" "$base_url/health/$kind.json" "$smoke_dir/$kind.json"; done
jq -e --argjson expected "$expected_dataset_count" '.schema == "datapulse/v1/dataset-trends" and (.datasets|type == "array" and length == $expected) and (.summary.datasets_total == $expected)' "$smoke_dir/trends.json" >/dev/null || fail "served trends are invalid"
jq -e --argjson expected "$expected_dataset_count" '.schema == "datapulse/v1/dataset-drift" and (.datasets|type == "array" and length == $expected) and (.summary.datasets_total == $expected)' "$smoke_dir/drift.json" >/dev/null || fail "served drift is invalid"
jq -e --argjson expected "$expected_dataset_count" '.schema == "datapulse/v1/dataset-reconciliation" and (.summary.datasets_total == $expected) and (.summary.datasets_grouped + .summary.datasets_single_source == $expected)' "$smoke_dir/reconciliation.json" >/dev/null || fail "served reconciliation is invalid"
fetch "MCP inventory" "$base_url/mcp.json" "$smoke_dir/mcp.json"; jq -e '.tools | type == "array" and length > 0 and all(.[]; type == "object" and (.name | type == "string" and length > 0) and (.inputSchema | type == "object"))' "$smoke_dir/mcp.json" >/dev/null || fail "served MCP inventory is invalid"
fetch "LLM index" "$base_url/llms.txt" "$smoke_dir/llms.txt"; grep -Fxq '<!-- BEGIN mcp-tools -->' "$smoke_dir/llms.txt" || fail "served llms index has no MCP tools block"; grep -Fxq '<!-- END mcp-tools -->' "$smoke_dir/llms.txt" || fail "served llms index has incomplete MCP tools block"
