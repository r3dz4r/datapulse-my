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

- [Manifest](https://r3dz4r.github.io/datapulse-my/datapulse.json)
- [Health](https://r3dz4r.github.io/datapulse-my/health/latest.json)
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
