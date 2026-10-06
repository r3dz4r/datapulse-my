#!/usr/bin/env bash
#
# Refresh the legacy attestation chain head ahead of Sigstore signing.
#
# gen_attestations.py owns validated reuse, immutable same-day append, and the
# latest/legacy projections. A head describes its set's recorded observation;
# later catalogue changes must never reinterpret an earlier signed receipt.
# Sigstore signing separately checks the candidate against current health.
#
set -Eeuo pipefail

if (( $# > 1 )); then
  printf 'refresh_chain_head.sh: expected at most one argument: the private-key JSON path\n' >&2
  exit 2
fi

private_key="${1:-${DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE:-}}"
if [[ -z "$private_key" ]]; then
  printf 'refresh_chain_head.sh: DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE is not set and no private-key path argument was given; refusing to refresh the chain head without a signing key\n' >&2
  exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

# The generator owns validated reuse and append; the shell has no date shortcut.
generate_args=(--root . --private-key "$private_key")
if [[ -n "${DATAPULSE_REKOR_REFERENCE:-}" ]]; then
  generate_args+=(--rekor-reference "$DATAPULSE_REKOR_REFERENCE")
fi
python3 scripts/gen_attestations.py "${generate_args[@]}"

cmp attestations/latest/chain_head.json .attestations/chain_head.json
observed_count="$(jq -er '.payload.health.dataset_count | select(type == "number" and . > 0 and . == floor)' attestations/latest/binding.json)"
head_count="$(jq -er '.payload.dataset_count | select(type == "number" and . > 0 and . == floor)' .attestations/chain_head.json)"
if [[ "$observed_count" != "$head_count" ]]; then
  printf 'refresh_chain_head.sh: refreshed chain head dataset_count (%s) does not match recorded health observation (%s)\n' "$head_count" "$observed_count" >&2
  exit 1
fi
