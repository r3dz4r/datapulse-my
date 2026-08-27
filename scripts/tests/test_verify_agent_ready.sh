#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture_root="$(mktemp -d)"
trap 'rm -rf "$fixture_root"' EXIT
mkdir -p "$fixture_root/health"

cat > "$fixture_root/llms.txt" <<'EOF'
# Fixture agent index

> A local two-row verification fixture.

## Machine-readable surfaces

- [Manifest](https://www.data-pulse.my/datapulse.json)
- [Health](https://www.data-pulse.my/health/latest.json)
EOF

cat > "$fixture_root/datapulse.json" <<'EOF'
{
  "datasets": [
    {"id": "alpha", "name": "Alpha", "licence": "CC BY 4.0"},
    {"id": "beta", "name": "Beta", "licence": "OGL"}
  ]
}
EOF

cat > "$fixture_root/health/latest.json" <<'EOF'
{
  "checked_at": "2026-08-08T00:00:00Z",
  "_trust_summary": {
    "datasets_total": 2,
    "by_status": {"fresh": 1, "stale": 1}
  },
  "datasets": [
    {"dataset_id": "alpha", "status": "fresh"},
    {"dataset_id": "beta", "status": "stale"}
  ]
}
EOF

mkdir -p "$fixture_root/attestations/latest" "$fixture_root/docs/.well-known"
cat > "$fixture_root/docs/.well-known/datapulse-probe-keys.json" <<'EOF'
{"schema":"datapulse/v1/probe-key-registry","keys":[{"key_id":"fixture"}]}
EOF
cat > "$fixture_root/attestations/latest/index.json" <<'EOF'
{"schema":"datapulse/v1/attestation-index","attestations":{"alpha":"attestations/alpha.json","beta":"attestations/beta.json"}}
EOF
cat > "$fixture_root/attestations/latest/chain_head.json" <<'EOF'
{"schema":"datapulse/v1/daily-chain-head-envelope","chain_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","dataset_links":[{},{}]}
EOF
cat > "$fixture_root/attestations/latest/scores.json" <<'EOF'
{"schema":"datapulse/v1/trust-scores","methodology_version":3,"datasets":[{"dataset_id":"alpha","methodology_version":3,"components":{"freshness":100},"component_availability":{"freshness":{"available":true,"reason":"measured"}}},{"dataset_id":"beta","methodology_version":3,"components":{"freshness":20},"component_availability":{"freshness":{"available":true,"reason":"classified"}}}]}
EOF
cat > "$fixture_root/attestations/alpha.json" <<'EOF'
{"schema":"datapulse/v1/probe-attestation-envelope","payload":{"key_id":"fixture"},"chain_link":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
EOF

if grep -Eq '(^|[^0-9])166([^0-9]|$)' "$repo_root/scripts/verify_agent_ready.sh"; then
  printf 'verify_agent_ready.sh still contains the fixed total 166\n' >&2
  exit 1
fi

output="$(
  DATAPULSE_AGENT_ROOT="$fixture_root" \
    DATAPULSE_AGENT_BASE_URL="http://127.0.0.1:1" \
    bash "$repo_root/scripts/verify_agent_ready.sh" --local
)"

grep -Fq '2 manifest datasets match 2 health records' <<<"$output"
grep -Fq 'Fresh datasets (status=fresh): 1/2' <<<"$output"
printf 'verify_agent_ready local derived-count test: PASS\n'

public_fixture_root="$fixture_root/public"
mkdir -p "$public_fixture_root/health"
cp "$fixture_root/llms.txt" "$public_fixture_root/llms.txt"
cp "$fixture_root/datapulse.json" "$public_fixture_root/datapulse.json"
cp "$fixture_root/health/latest.json" "$public_fixture_root/health/latest.json"

fake_bin="$fixture_root/bin"
mkdir -p "$fake_bin"
cat > "$fake_bin/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
output=""
url=""
retry=""
delay=""
all_errors=false
while (( $# > 0 )); do
  case "$1" in
    --retry) retry="$2"; shift 2 ;;
    --retry-delay) delay="$2"; shift 2 ;;
    --retry-all-errors) all_errors=true; shift ;;
    --connect-timeout|--max-time) shift 2 ;;
    --output) output="$2"; shift 2 ;;
    *) url="$1"; shift ;;
  esac
done
[[ "$retry" == "12" && "$delay" == "15" && "$all_errors" == true ]]
path="${url#https://example.invalid/}"
for ((attempt = 1; attempt <= retry + 1; attempt++)); do
  printf '%s %s\n' "$path" "$attempt" >> "$MOCK_CURL_LOG"
  if [[ "$MOCK_CURL_MODE" != "fail" && "$attempt" -ge 3 ]]; then
    break
  fi
  if (( attempt == 1 )); then printf '404\n' >&2; else printf '503\n' >&2; fi
done
if [[ "$MOCK_CURL_MODE" == "fail" ]]; then
  exit 22
fi
case "$path" in
  llms.txt) cp "$MOCK_CURL_FIXTURE_ROOT/llms.txt" "$output" ;;
  datapulse.json) cp "$MOCK_CURL_FIXTURE_ROOT/datapulse.json" "$output" ;;
  health/latest.json) cp "$MOCK_CURL_FIXTURE_ROOT/health/latest.json" "$output" ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$fake_bin/curl"

retry_state="$fixture_root/retry-state"
retry_log="$fixture_root/retry.log"
mkdir -p "$retry_state"
retry_output="$(
  PATH="$fake_bin:$PATH" \
    MOCK_CURL_FIXTURE_ROOT="$public_fixture_root" \
    MOCK_CURL_LOG="$retry_log" \
    MOCK_CURL_STATE_DIR="$retry_state" \
    MOCK_CURL_MODE=recover \
    DATAPULSE_AGENT_ROOT="$fixture_root" \
    DATAPULSE_AGENT_BASE_URL="https://example.invalid" \
    bash "$repo_root/scripts/verify_agent_ready.sh"
)" || {
  cat "$retry_log" >&2
  exit 1
}
grep -Fq '2 manifest datasets match 2 health records' <<<"$retry_output"
grep -Fq 'llms.txt 1' "$retry_log"
grep -Fq 'llms.txt 3' "$retry_log"
grep -Fq 'datapulse.json 3' "$retry_log"
grep -Fq 'health/latest.json 3' "$retry_log"
printf 'verify_agent_ready public 404/503 recovery test: PASS\n'

rejected_fixture_root="$fixture_root/rejected-public"
mkdir -p "$rejected_fixture_root"
# Negative fixture by purpose: inject the retired GitHub Pages host into the
# otherwise-canonical index and prove the verifier rejects non-canonical hosts.
sed 's#https://www.data-pulse.my#https://r3dz4r.github.io/datapulse-my#g' \
  "$public_fixture_root/llms.txt" > "$rejected_fixture_root/llms.txt"
rejected_log="$fixture_root/rejected.log"
if PATH="$fake_bin:$PATH" \
  MOCK_CURL_FIXTURE_ROOT="$rejected_fixture_root" \
  MOCK_CURL_LOG="$rejected_log" \
  MOCK_CURL_MODE=recover \
  DATAPULSE_AGENT_ROOT="$fixture_root" \
  DATAPULSE_AGENT_BASE_URL="https://example.invalid" \
  bash "$repo_root/scripts/verify_agent_ready.sh" >"$fixture_root/rejected.out" 2>"$fixture_root/rejected.err"; then
  printf 'verify_agent_ready retired Pages host unexpectedly passed\n' >&2
  exit 1
fi
grep -Fq 'Discovered URLs are outside the canonical DataPulse MY host' "$fixture_root/rejected.err"
[[ "$(grep -c '^llms.txt ' "$rejected_log")" -eq 3 ]]
! grep -Eq '^(datapulse.json|health/latest.json) ' "$rejected_log"
printf 'verify_agent_ready non-canonical host rejection test: PASS\n'

failure_state="$fixture_root/failure-state"
failure_log="$fixture_root/failure.log"
mkdir -p "$failure_state"
if PATH="$fake_bin:$PATH" \
  MOCK_CURL_FIXTURE_ROOT="$public_fixture_root" \
  MOCK_CURL_LOG="$failure_log" \
  MOCK_CURL_STATE_DIR="$failure_state" \
  MOCK_CURL_MODE=fail \
  DATAPULSE_AGENT_BASE_URL="https://example.invalid" \
  bash "$repo_root/scripts/verify_agent_ready.sh" >"$fixture_root/failure.out" 2>"$fixture_root/failure.err"; then
  printf 'verify_agent_ready persistent public failure unexpectedly passed\n' >&2
  exit 1
fi
grep -Fq 'Failed to fetch agent index from https://example.invalid/llms.txt after 13 attempts' "$fixture_root/failure.err"
[[ "$(wc -l < "$failure_log")" -eq 13 ]]
printf 'verify_agent_ready persistent retry exhaustion test: PASS\n'
