#!/usr/bin/env bash
# Verify one assembled Pages artifact at an explicit HTTPS origin.  This is used
# for both the isolated preview promotion gate and the post-production readback.
set -Eeuo pipefail

usage() {
  echo "usage: $0 --base-url URL --site DIR --sigstore-signed true|false --health-only true|false --source-commit SHA [--sigstore-publication DIR] [--cosign PATH] [--kv-surfaces-published-elsewhere]" >&2
  echo "  --sigstore-publication is required for accepted reports and when --sigstore-signed true" >&2
  echo "  --kv-surfaces-published-elsewhere skips served /health/ namespace checks" >&2
  echo "    for unsigned build previews; accepted reports always require exact health bytes" >&2
  exit 64
}

base_url="${DATAPULSE_SERVED_BASE_URL:-}"
site_dir="${DATAPULSE_SITE_DIR:-_site}"
sigstore_signed="${DATAPULSE_SIGSTORE_SIGNED:-}"
health_only="${DATAPULSE_HEALTH_ONLY:-}"
publication_dir="${DATAPULSE_SIGSTORE_PUBLICATION_DIR:-}"
source_commit="${DATAPULSE_SOURCE_COMMIT:-${GITHUB_SHA:-}}"
cosign_bin="${DATAPULSE_COSIGN:-}"
# The /health/ namespace is published by another lane on its own cadence. A
# preview lane with no KV write credential opts in to excluding its served
# fetches and comparisons; strict mode still verifies every surface.
kv_surfaces_published_elsewhere=false
# This must exceed the time needed to move the largest declared surface, even
# when the response is compressed on the wire but slow to arrive.
fetch_max_time="${FETCH_MAX_TIME:-120}"
while (($#)); do
  case "$1" in
    --base-url) base_url="$2"; shift 2 ;;
    --site) site_dir="$2"; shift 2 ;;
    --sigstore-signed) sigstore_signed="$2"; shift 2 ;;
    --health-only) health_only="$2"; shift 2 ;;
    --sigstore-publication) publication_dir="$2"; shift 2 ;;
    --source-commit) source_commit="$2"; shift 2 ;;
    --cosign) cosign_bin="$2"; shift 2 ;;
    --kv-surfaces-published-elsewhere) kv_surfaces_published_elsewhere=true; shift ;;
    *) usage ;;
  esac
done
fail() { echo "::error title=Cloudflare Pages contract failed::$1"; exit 1; }
[[ "$base_url" =~ ^https://[^/:[:space:]]+(:[0-9]+)?$ ]] || fail "invalid served base URL"
[[ -d "$site_dir" && -s "$site_dir/health/latest.json" ]] || fail "assembled site is missing health/latest.json"
[[ "$sigstore_signed" == true || "$sigstore_signed" == false ]] || fail "invalid Sigstore signing result"
[[ "$health_only" == true || "$health_only" == false ]] || fail "invalid health-only mode"
[[ "$kv_surfaces_published_elsewhere" == true || "$kv_surfaces_published_elsewhere" == false ]] || fail "invalid KV surface exclusion"
[[ -n "$source_commit" ]] || fail "missing staged signing inputs"
# The publication directory stages the signed bundle and manifest this verifier
# compares the served bytes against. It is a signing input, so require it when
# signing is declared true and not otherwise: an unsigned origin carries no
# signature to compare, and demanding the directory for an unsigned run would
# imply the served surface is signed when it is not.
if [[ "$sigstore_signed" == true && -z "$publication_dir" ]]; then
  fail "missing staged signing inputs"
fi
accepted_report=false
if [[ -n "$publication_dir" || -f "$site_dir/publication-identity.json" ]]; then
  accepted_report=true
  [[ -n "$publication_dir" && -s "$publication_dir/publication-identity.json" ]] || fail "missing staged accepted report identity"
  cmp -s "$publication_dir/publication-identity.json" "$site_dir/publication-identity.json" || fail "assembled accepted report identity differs from staged artifact"
  # The code build and the accepted observation have independent clocks. Keep
  # the entire assembled byte inventory pinned to the selected code revision.
  python3 scripts/verify_release_artifact.py verify --site "$site_dir" \
    --manifest "$RUNNER_TEMP/release-artifact-manifest.json" \
    --source-commit "$source_commit" || fail "accepted publication build identity drift"
fi
smoke_dir="$(mktemp -d)"
trap 'rm -rf "$smoke_dir"' EXIT
fetch() {
  local surface="$1" url="$2" output="$3"
  [[ "$url" =~ ^https://[^[:space:]]+$ ]] || fail "invalid URL for $surface"
  mkdir -p "$(dirname "$output")"
  retrieve "$surface" "$url" "$output" "" || fail "transport failure retrieving $surface: curl exit code $last_curl_status, elapsed_seconds=$last_elapsed, bytes received=$last_bytes"
  [[ "$last_status" == 2?? ]] || fail "missing or stale served surface: $surface (HTTP $last_status)"
}
retrieve() {
  local surface="$1" url="$2" output="$3" headers="$4" follow_redirects="${5:-true}" metrics
  local -a curl_args=(--silent --show-error --proto '=https' --compressed --retry 3 --retry-delay 5 --retry-all-errors --connect-timeout 10 --max-time "$fetch_max_time" --output "$output" --write-out '%{http_code} %{time_total} %{size_download}')
  [[ "$follow_redirects" == true ]] && curl_args+=(--location)
  [[ -n "$headers" ]] && curl_args+=(--dump-header "$headers")
  if metrics="$(curl "${curl_args[@]}" "$url")"; then
    last_curl_status=0
  else
    last_curl_status=$?
  fi
  read -r last_status last_elapsed last_bytes <<<"${metrics:-000 0 0}"
  echo "served surface=$surface bytes=$last_bytes elapsed_seconds=$last_elapsed http_status=$last_status"
  [[ "$last_curl_status" -eq 0 ]]
}
fetch_alias() {
  local surface="$1" url="$2" target="${3:-}" requested_path headers body resolved_headers resolved_body location location_path accepted declared_alias_path status
  requested_path="${url#"$base_url"}"; headers="$smoke_dir/${surface// /-}.headers"; body="$smoke_dir/${surface// /-}.body"; resolved_headers="$smoke_dir/${surface// /-}.resolved.headers"; resolved_body="$smoke_dir/${surface// /-}.resolved.body"
  [[ "$url" =~ ^https://[^[:space:]]+$ ]] || fail "invalid URL for $surface"
  retrieve "$surface" "$url" "$body" "$headers" false || fail "transport failure retrieving $surface: curl exit code $last_curl_status, elapsed_seconds=$last_elapsed, bytes received=$last_bytes"; status="$last_status"
  location="$(awk 'tolower($1) == "location:" { sub(/[\r ]+$/, "", $2); print $2; exit }' "$headers")"; [[ "$location" == "${location%#}" ]] || location="${location%#}"
  if [[ -n "$location" ]]; then
    [[ "$status" == 308 ]] || fail "$surface uses an unexpected edge redirect to ${location}"
    case "$location" in
      "$base_url"/*) location_path="${location#"$base_url"}" ;;
      /*) location_path="$location" ;;
      *) fail "$surface normalizes to an unexpected location: ${location}" ;;
    esac
    [[ "$location_path" =~ ^/[A-Za-z0-9._/-]*$ && "$location_path" != //* && "$location_path" != *".."* ]] || fail "$surface normalizes to an unexpected location: ${location}"
    accepted=false
    [[ -n "$target" && "$location_path" == "$target" ]] && accepted=true
    if [[ "$accepted" != true && "$location_path" != "$requested_path" ]]; then
      while IFS= read -r declared_alias_path; do
        [[ "$declared_alias_path" == "$location_path" ]] && { accepted=true; break; }
      done < <(jq -r '.compatibility_aliases[]?.path' config/public-surfaces.json)
    fi
    [[ "$accepted" == true ]] || fail "$surface normalizes to an unexpected location: ${location}"
    retrieve "$surface normalized" "$base_url$location_path" "$resolved_body" "$resolved_headers" false || fail "transport failure retrieving normalized compatibility alias $surface: curl exit code $last_curl_status, elapsed_seconds=$last_elapsed, bytes received=$last_bytes"; status="$last_status"
    [[ "$status" == 200 ]] || fail "$surface normalized alias returned HTTP $status"
    location="$(awk 'tolower($1) == "location:" { sub(/[\r ]+$/, "", $2); print $2; exit }' "$resolved_headers")"; [[ -z "$location" ]] || fail "$surface normalized alias redirects again to ${location}"; body="$resolved_body"
  else [[ "$status" == 200 ]] || fail "$surface returned unexpected HTTP $status"; fi
  grep -Fq '<title>DataPulse dataset register</title>' "$body" || fail "$surface lacks alias document identity"
  grep -Fq '<link rel="canonical" href="/">' "$body" || fail "$surface lacks root canonical identity"
  grep -Fq 'http-equiv="refresh" content="0; url=/"' "$body" || fail "$surface lacks root browser fallback"
  grep -Fq 'href="/">DataPulse dataset register</a>' "$body" || fail "$surface lacks accessible root fallback"
}
# A declared surface is a promise, but HTTP 200 is not proof: this site answers
# unknown paths with its SPA fallback HTML.  Machine-evidence surfaces must
# parse as JSON and carry their declared schema marker, or the deploy fails.
verify_declared_surface_content() {
  local surface="$1" body="$2"
  [[ "$surface" == /observation-receipts/chain_head.json ]] || return 0
  jq -e '.schema == "datapulse/v1/observation-chain-head"' "$body" >/dev/null || fail "declared observation receipt surface $surface does not serve the datapulse/v1/observation-chain-head schema (SPA fallback?)"
}
verify_attestation_surface() {
  local path="$1" body="$smoke_dir/attestation-plane/$1" accepted expected
  shift
  if [[ -f "$site_dir/$path" ]]; then
    fetch "attestation plane $path" "$base_url/$path" "$body"
    cmp -s "$site_dir/$path" "$body" || fail "attestation plane $path differs from assembled artifact"
    # Most paths pin exactly one schema. The chain index accepts a set: the
    # producer now emits v2 while already-published sets remain v1, and history
    # must stay readable. No other path takes more than one.
    if (($#)); then
      accepted="$(jq -cn --args '$ARGS.positional' "$@")"
      jq -e --argjson accepted "$accepted" '.schema as $schema | ($accepted | index($schema)) != null' "$body" >/dev/null || {
        expected="$*"; (($# == 1)) || expected="${1} or ${*:2}"
        fail "attestation plane $path lacks $expected schema"
      }
    fi
  else
    mkdir -p "$(dirname "$body")"
    retrieve "attestation plane $path (absent)" "$base_url/$path" "$body" "" || fail "transport failure retrieving attestation plane $path: curl exit code $last_curl_status, elapsed_seconds=$last_elapsed, bytes received=$last_bytes"
    [[ "$last_status" == 404 ]] || fail "attestation plane $path must be absent but served HTTP $last_status"
  fi
}
verify_dataset_attestation() {
  local reference="$1" omissions omitted
  if [[ ! -f "$site_dir/$reference" ]]; then
    # The selector records intentional dataset omissions in the assembled artifact.
    # Absence alone cannot waive a required file or an unexpected remote 404.
    if [[ "${retention_loaded:-false}" != true ]]; then
      declare -gA not_served_attestations=()
      omissions="$(jq -r 'if .schema == "datapulse/v1/served-attestation-retention" then .not_served[] else error("invalid retention inventory") end' "$site_dir/attestations/served-retention.json")" || fail "assembled attestation plane retention inventory is invalid"
      while IFS= read -r omitted; do
        [[ -z "$omitted" ]] || not_served_attestations["$omitted"]=1
      done <<< "$omissions"
      retention_loaded=true
    fi
    [[ "${not_served_attestations[$reference]:-}" == 1 ]] || fail "assembled attestation plane is missing required evidence: $reference"
    # Its inventory is fetched and byte-compared once. Do not dereference thousands
    # of intentionally pruned historical URLs just to rediscover their absence.
    echo "attestation plane $reference: not served (retention policy)"
  else
    verify_attestation_surface "$reference"
  fi
}
verify_attestation_plane() {
  local index_date head_ref head_refs set_dir set_index reference references
  verify_attestation_surface attestations/latest/index.json datapulse/v1/attestation-index
  verify_attestation_surface attestations/latest/chain_head.json datapulse/v1/daily-chain-head-envelope
  verify_attestation_surface attestations/latest/binding.json datapulse/v1/attestation-binding-envelope
  verify_attestation_surface attestations/latest/scores.json
  verify_attestation_surface attestations/chain-index.json datapulse/v1/chain-index datapulse/v2/chain-index
  verify_attestation_surface attestations/served-retention.json datapulse/v1/served-attestation-retention
  verify_attestation_surface .well-known/datapulse-probe-keys.json datapulse/v2/probe-key-registry

  [[ -f "$site_dir/attestations/latest/index.json" ]] || fail "assembled attestation plane is missing attestations/latest/index.json"
  [[ -f "$site_dir/attestations/chain-index.json" ]] || fail "assembled attestation plane is missing attestations/chain-index.json"
  index_date="$(jq -er '.date | select(type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$"))' "$site_dir/attestations/latest/index.json")" || fail "assembled attestation plane index date is invalid"
  head_refs="$(jq -er --arg prefix "attestations/${index_date}/" '.heads | to_entries[] | .value | select(startswith($prefix))' "$site_dir/attestations/chain-index.json")" || fail "assembled attestation plane chain index has no head for $index_date"
  while IFS= read -r head_ref; do
    [[ -z "$head_ref" ]] && continue
    [[ "$head_ref" =~ ^attestations/${index_date}/(revisions/[0-9a-f]{64}/)?chain_head\.json$ ]] || fail "attestation plane chain head reference is unsafe: $head_ref"
    set_dir="${head_ref%/chain_head.json}"
    [[ -f "$site_dir/$set_dir/chain_head.json" ]] || fail "assembled attestation plane is missing $set_dir/chain_head.json"
    [[ -f "$site_dir/$set_dir/binding.json" ]] || fail "assembled attestation plane is missing $set_dir/binding.json"
    verify_attestation_surface "$set_dir/chain_head.json" datapulse/v1/daily-chain-head-envelope
    verify_attestation_surface "$set_dir/binding.json" datapulse/v1/attestation-binding-envelope
    verify_attestation_surface "$set_dir/index.json" datapulse/v1/attestation-index
    verify_attestation_surface "$set_dir/health.json"
    set_index="$site_dir/$set_dir/index.json"
    if [[ ! -f "$set_index" ]]; then
      set_index="$site_dir/attestations/latest/index.json"
    fi
    references="$(jq -er '.attestations | to_entries[] | .value' "$set_index")" || fail "assembled attestation plane set index is invalid: $set_index"
    while IFS= read -r reference; do
      [[ -z "$reference" ]] && continue
      [[ "$reference" =~ ^${set_dir}/[A-Za-z0-9_.-]+\.json$ ]] || fail "attestation plane dataset reference is unsafe: $reference"
      verify_dataset_attestation "$reference"
    done <<< "$references"
  done <<< "$head_refs"
}
# Permit Pages propagation at either origin before comparing exact served bytes.
sleep 30
expected_dataset_count="$(jq -er '.datasets | select(type == "array" and length > 0) | length' "$site_dir/datapulse.json")" || fail "assembled manifest has no dataset array"
fetch "dataset register" "$base_url/" "$smoke_dir/index.html"
grep -q '<title>DataPulse Dataset Register</title>' "$smoke_dir/index.html" || fail "origin root is not the DataPulse dataset register"
grep -Fq "'/health/index.json'" "$smoke_dir/index.html" || fail "origin root does not fetch the dashboard health projection"
observed_register_rows="$(grep -o '<article class="register-row' "$smoke_dir/index.html" | wc -l)"; [[ "$observed_register_rows" -eq "$expected_dataset_count" ]] || fail "origin root register rows mismatch: expected $expected_dataset_count, observed $observed_register_rows"
grep -q 'DataPulse MY' "$smoke_dir/index.html" && fail "origin root retains the retired product-name alias"
fetch_alias landing.html "$base_url/landing.html" /; fetch_alias landing "$base_url/landing" /; fetch_alias dashboard "$base_url/dashboard" /; fetch_alias register "$base_url/register" /
if [[ "$kv_surfaces_published_elsewhere" != true || "$accepted_report" == true ]]; then
fetch "health snapshot" "$base_url/health/latest.json" "$smoke_dir/health/latest.json"
python3 - "$site_dir/health/latest.json" "$smoke_dir/health/latest.json" <<'PY'
import hashlib,sys
from pathlib import Path
digests = [hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in sys.argv[1:]]
if digests[0] != digests[1]:
 raise SystemExit('served health digest differs from the accepted report bytes')
PY
fi
if [[ "$accepted_report" == true ]]; then
  fetch "accepted publication identity" "$base_url/publication-identity.json" "$smoke_dir/publication-identity.json"
  cmp -s "$publication_dir/publication-identity.json" "$smoke_dir/publication-identity.json" || fail "served accepted report identity differs from staged artifact"
  fetch "accepted report binding" "$base_url/attestations/latest/binding.json" "$smoke_dir/report-binding.json"
  cmp -s "$publication_dir/attestations/latest/binding.json" "$smoke_dir/report-binding.json" || fail "served accepted report binding differs from staged artifact"
  python3 - "$smoke_dir" "$source_commit" <<'PY'
import json,sys
from datetime import datetime, timezone
from pathlib import Path
from scripts.select_accepted_health import report_age

served = Path(sys.argv[1])
identity = json.loads((served / 'publication-identity.json').read_bytes())
binding = json.loads((served / 'report-binding.json').read_bytes())['payload']
age = report_age(served / 'health/latest.json', served / 'report-binding.json', datetime.now(timezone.utc))
if (identity['accepted_main_commit'] != sys.argv[2]
        or identity['health_sha256'] != binding['health']['artifact_sha256']
        or identity['dataset_count'] != binding['health']['dataset_count']
        or identity['accepted_chain_head'] != binding['ed25519']['chain_head']
        or identity['observed_at'] != age['observed_at']
        or identity['published_at'] != age['published_at']
        or identity['max_age_seconds'] != age['max_age_seconds']):
 raise SystemExit('accepted report identity drift')
print('Report age: ' + json.dumps(age, sort_keys=True))
if age['report_age_status'] != 'current':
 raise SystemExit('accepted report exceeds 36-hour signed policy or has future timestamps')
PY
fi
if [[ "$kv_surfaces_published_elsewhere" != true ]]; then
fetch "dashboard health projection" "$base_url/health/index.json" "$smoke_dir/health/index.json"
fi
sigstore_path="signatures/health.latest.sigstore.json"
if [[ "$sigstore_signed" == true ]]; then
  staged_bundle="$publication_dir/health.latest.sigstore.json"; staged_manifest="$publication_dir/datapulse.json"; test -s "$staged_bundle" || fail "verified Sigstore bundle is missing from the deploy job"; test -s "$staged_manifest" || fail "signed manifest snapshot is missing from the deploy job"
  fetch "Sigstore health DSSE bundle" "$base_url/$sigstore_path" "$smoke_dir/health.latest.sigstore.json"; cmp -s "$staged_bundle" "$smoke_dir/health.latest.sigstore.json" || fail "served Sigstore bundle differs from the verified staged artifact"
  fetch "signed manifest snapshot" "$base_url/signatures/datapulse.json" "$smoke_dir/signatures/datapulse.json"; cmp -s "$staged_manifest" "$smoke_dir/signatures/datapulse.json" || fail "served signed manifest snapshot differs from the verified staged artifact"
  [[ -n "$cosign_bin" && -x "$cosign_bin" ]] || fail "Cosign verifier is required for a signed bundle"
  python3 scripts/verify_sigstore_bundle.py --health "$site_dir/health/latest.json" --manifest "$smoke_dir/signatures/datapulse.json" --legacy-chain-head "$publication_dir/chain_head.json" --source-commit "$source_commit" --bundle "$smoke_dir/health.latest.sigstore.json" --certificate-identity "https://github.com/r3dz4r/datapulse-my/.github/workflows/deploy-cloudflare-pages.yml@refs/heads/main" --certificate-oidc-issuer "https://token.actions.githubusercontent.com" --cosign "$cosign_bin" || fail "served Sigstore bundle verification failed"
else
  retrieve "optional Sigstore health DSSE bundle" "$base_url/$sigstore_path" "$smoke_dir/unsigned-sigstore-response" "" || fail "transport failure retrieving optional Sigstore health DSSE bundle: curl exit code $last_curl_status, elapsed_seconds=$last_elapsed, bytes received=$last_bytes"; status="$last_status"
  if [[ "$status" == 200 ]]; then grep -q 'application/vnd.dev.sigstore.bundle' "$smoke_dir/unsigned-sigstore-response" && fail "stale Sigstore bundle is still served after signing became unavailable (HTTP $status)"; grep -Eq '<html[ >]|<head>|id="main-content"|hero-heading' "$smoke_dir/unsigned-sigstore-response" || fail "stale Sigstore bundle is still served after signing became unavailable (HTTP $status)"; elif [[ "$status" == 404 ]]; then :; else fail "unexpected HTTP status while proving optional Sigstore bundle absence (HTTP $status)"; fi
fi
if [[ "$health_only" == true ]]; then staged_proof="$RUNNER_TEMP/preserved-release-proof/release-verification.md"; else staged_proof="docs/release-verification.md"; fi
test -s "$staged_proof" || fail "staged release proof is missing"; fetch "release reproducibility proof" "$base_url/release-verification.md" "$smoke_dir/release-verification.md"; cmp -s "$staged_proof" "$smoke_dir/release-verification.md" || fail "served release proof differs from staged artifact"
python3 - "$smoke_dir/release-verification.md" "$source_commit" mcp.json "$health_only" <<'PY'
import json,re,sys
from pathlib import Path
proof, sha, mcp_path, health_only=sys.argv[1:]; contents=Path(proof).read_text(encoding='utf-8')
if health_only == 'true':
 required={'release-proof title':r'^# Release reproducibility verification$','verification timestamp':r'^- (?:Generated|Verified) at: `[^`\\n]+`$','Source SHA':r'^- Source SHA: `[0-9a-f]{7,64}`$','Profile result':r'^- Profile result: .+$','Total files built':r'^- Total files built: .+$','hash table':r'^\\| Path category \\| File count \\| First-run hash \\| Second-run hash \\| Match\\? \\|$','hash table category row':r'^\\| (?![-: ]+\\|)[^|]+ \\| \\d+ \\|','Reproduction section':r'^## Reproduction$'}; missing=[k for k,v in required.items() if not re.search(v,contents,re.M)]
else:
 tools=json.loads(Path(mcp_path).read_text())['tools']; required=('<!-- generated: scripts/verify_release_reproducible.py; do not hand-edit -->','- Status: `current generated release proof`',f'- Source SHA: `{sha}`',f'- MCP tool count: `{len(tools)}`','- Protocol result: `byte-identical isolated release-build runs`'); missing=[v for v in required if v not in contents]
# A build may be newer and have a different dataset count than the accepted
# observation it publishes. Report digest, membership and signed age are checked
# above; this proof independently identifies the reproducible code build.
if missing: raise SystemExit('release proof drift: '+'; '.join(missing))
PY
mapfile -t pages < <(jq -er '.pages[]' config/public-surfaces.json); mapfile -t artifacts < <(jq -er '.artifacts[]' config/public-surfaces.json)
excluded_health_paths=(/health/latest.json /health/index.json)
declare -A excluded_health_seen=([/health/latest.json]=1 [/health/index.json]=1)
for path in "${pages[@]}" "${artifacts[@]}"; do
  [[ "$path" == / || "$path" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail "unsafe declared public path: $path"
  # Resolve collections before excluding the path we would fetch. Declared
  # health collections remain excludable even when absent from the local site.
  if [[ "$path" == */ && ( "$kv_surfaces_published_elsewhere" != true || "$path" != /health/* ) ]]; then declared_file="$(find "$site_dir${path}" -type f -print -quit)" || fail "declared collection is missing: $path"; [[ -n "$declared_file" ]] || fail "declared collection is empty: $path"; path="/${declared_file#"$site_dir/"}"; fi
  # A preview does not own the served /health/ namespace, including paths
  # added to the declaration after this verifier was written.
  if [[ "$kv_surfaces_published_elsewhere" == true && "$path" == /health/* ]]; then
    if [[ -z "${excluded_health_seen[$path]:-}" ]]; then
      excluded_health_paths+=("$path")
      excluded_health_seen["$path"]=1
    fi
    continue
  fi
  fetch "declared public surface $path" "$base_url$path" "$smoke_dir/surfaces${path%/}/index"
  verify_declared_surface_content "$path" "$smoke_dir/surfaces${path%/}/index"
done
if [[ "$kv_surfaces_published_elsewhere" == true ]]; then
  excluded_health_list="$(printf '%s, ' "${excluded_health_paths[@]}")"
  echo "::warning title=KV-backed health surfaces published elsewhere::KV-backed surfaces published by another lane on its own cadence were not fetched or compared: ${excluded_health_list%, }; all non-/health/ declared public surfaces retain their served checks; accepted report digest and signed age checks remain mandatory"
fi
verify_attestation_plane
if [[ "$kv_surfaces_published_elsewhere" != true ]]; then
python3 - "$smoke_dir/index.html" "$smoke_dir/health/index.json" "$smoke_dir/health/latest.json" <<'PY'
import json,sys
from pathlib import Path
dashboard=Path(sys.argv[1]).read_text(); projection=json.loads(Path(sys.argv[2]).read_text()); health=json.loads(Path(sys.argv[3]).read_text())
if "'/health/index.json'" not in dashboard: raise SystemExit('dashboard does not fetch the served health projection')
if not isinstance(projection,dict) or not isinstance(projection.get('datasets'),list): raise SystemExit('dashboard health projection has no dataset array')
if not (projection.get('checked_at') and health.get('checked_at')) or projection['checked_at'] < health['checked_at']: raise SystemExit('dashboard health projection is older than served health/latest.json (the edge copy must be at least as fresh as the deployed snapshot)')
if len(projection['datasets']) != len(health['datasets']): raise SystemExit('dashboard health projection dataset count differs from served health/latest.json')
if not all(isinstance(row,dict) and isinstance(row.get('dataset_id'),str) for row in projection['datasets']): raise SystemExit('dashboard health projection datasets are invalid')
if {row['dataset_id'] for row in projection['datasets']} != {row['dataset_id'] for row in health['datasets']}: raise SystemExit('dashboard health projection dataset IDs differ from served health/latest.json')
PY
fi
if [[ "$kv_surfaces_published_elsewhere" != true ]]; then
expected_dataset_count="$(jq -er '.datasets | select(type == "array" and length > 0) | length' "$smoke_dir/health/latest.json")" || fail "served health has no dataset array"
for kind in trends drift reconciliation; do fetch "$kind snapshot" "$base_url/health/$kind.json" "$smoke_dir/$kind.json"; done
jq -e --argjson expected "$expected_dataset_count" '.schema == "datapulse/v1/dataset-trends" and (.datasets|type == "array" and length == $expected) and (.summary.datasets_total == $expected)' "$smoke_dir/trends.json" >/dev/null || fail "served trends are invalid"
jq -e --argjson expected "$expected_dataset_count" '.schema == "datapulse/v1/dataset-drift" and (.datasets|type == "array" and length == $expected) and (.summary.datasets_total == $expected)' "$smoke_dir/drift.json" >/dev/null || fail "served drift is invalid"
jq -e --argjson expected "$expected_dataset_count" '.schema == "datapulse/v1/dataset-reconciliation" and (.summary.datasets_total == $expected) and (.summary.datasets_grouped + .summary.datasets_single_source == $expected)' "$smoke_dir/reconciliation.json" >/dev/null || fail "served reconciliation is invalid"
fi
fetch "MCP inventory" "$base_url/mcp.json" "$smoke_dir/mcp.json"; jq -e '.tools | type == "array" and length > 0 and all(.[]; type == "object" and (.name | type == "string" and length > 0) and (.inputSchema | type == "object"))' "$smoke_dir/mcp.json" >/dev/null || fail "served MCP inventory is invalid"
fetch "LLM index" "$base_url/llms.txt" "$smoke_dir/llms.txt"; grep -Fxq '<!-- BEGIN mcp-tools -->' "$smoke_dir/llms.txt" || fail "served llms index has no MCP tools block"; grep -Fxq '<!-- END mcp-tools -->' "$smoke_dir/llms.txt" || fail "served llms index has incomplete MCP tools block"
