#!/usr/bin/env bash
set -euo pipefail

local_mode=false
if [[ "${1:-}" == "--local" ]]; then
  local_mode=true
  shift
fi
if (( $# > 0 )); then
  printf 'Usage: %s [--local]\n' "$0" >&2
  exit 2
fi

canonical_base_url="https://r3dz4r.github.io/datapulse-my"
base_url="${DATAPULSE_AGENT_BASE_URL:-$canonical_base_url}"
base_url="${base_url%/}"
agent_root="${DATAPULSE_AGENT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

required_commands=(jq python3)
if ! $local_mode; then
  required_commands+=(curl)
fi
for command in "${required_commands[@]}"; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$command" >&2
    exit 1
  fi
done

work_dir="$(mktemp -d)"
llms_file="$work_dir/llms.txt"
manifest_file="$work_dir/datapulse.json"
health_file="$work_dir/health.json"
trap 'rm -rf "$work_dir"' EXIT

if $local_mode; then
  printf 'Reading local agent index: %s/llms.txt\n' "$agent_root"
  cp "$agent_root/llms.txt" "$llms_file"
else
  printf 'Fetching agent index: %s/llms.txt\n' "$base_url"
  curl --fail --location --silent --show-error \
    "$base_url/llms.txt" --output "$llms_file"
fi

if ! discovered_urls="$(python3 - "$llms_file" <<'PY'
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

text = Path(sys.argv[1]).read_text(encoding="utf-8")
if len(re.findall(r"^# ", text, re.MULTILINE)) != 1:
    raise SystemExit("llms.txt must contain exactly one H1")
if not re.search(r"^> ", text, re.MULTILINE):
    raise SystemExit("llms.txt must contain a blockquote summary")
if not re.search(r"^## ", text, re.MULTILINE):
    raise SystemExit("llms.txt must contain at least one H2 link-list section")

links = re.findall(r"\[[^]]+\]\(([^)]+)\)", text)
if not links:
    raise SystemExit("llms.txt contains no Markdown links")
for link in links:
    parsed = urlsplit(link)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit(f"llms.txt link is not an absolute HTTPS URL: {link}")

manifest_links = [link for link in links if urlsplit(link).path.endswith("/datapulse.json")]
health_links = [link for link in links if urlsplit(link).path.endswith("/health/latest.json")]
if len(manifest_links) != 1:
    raise SystemExit("llms.txt must contain exactly one datapulse.json link")
if len(health_links) != 1:
    raise SystemExit("llms.txt must contain exactly one health/latest.json link")

print(manifest_links[0])
print(health_links[0])
PY
)"; then
  exit 1
fi

manifest_url="$(sed -n '1p' <<<"$discovered_urls")"
health_url="$(sed -n '2p' <<<"$discovered_urls")"

if [[ -n "${DATAPULSE_AGENT_BASE_URL:-}" ]]; then
  if [[ "$manifest_url" != "$canonical_base_url/"* || "$health_url" != "$canonical_base_url/"* ]]; then
    printf 'Discovered URLs are outside the canonical DataPulse MY host\n' >&2
    exit 1
  fi
  manifest_url="$base_url/${manifest_url#"$canonical_base_url/"}"
  health_url="$base_url/${health_url#"$canonical_base_url/"}"
fi

if $local_mode; then
  printf 'Reading local manifest: %s/datapulse.json\n' "$agent_root"
  cp "$agent_root/datapulse.json" "$manifest_file"
  printf 'Reading local health snapshot: %s/health/latest.json\n' "$agent_root"
  cp "$agent_root/health/latest.json" "$health_file"
else
  printf 'Following manifest link: %s\n' "$manifest_url"
  curl --fail --location --silent --show-error "$manifest_url" --output "$manifest_file"
  printf 'Following health link: %s\n' "$health_url"
  curl --fail --location --silent --show-error "$health_url" --output "$health_file"
fi

if ! jq -e '
  (.datasets | type == "array" and length > 0) and
  ([.datasets[].id] | length == (unique | length)) and
  all(.datasets[];
    (.id | type == "string" and length > 0) and
    (.name | type == "string" and length > 0) and
    (.licence | type == "string" and length > 0)
  )
' "$manifest_file" >/dev/null; then
  printf 'Manifest is invalid or does not contain uniquely identified datasets\n' >&2
  exit 1
fi
manifest_count="$(jq -er '.datasets | length' "$manifest_file")"

if ! jq -e '
  (.datasets | length) as $dataset_count |
  (.checked_at | type == "string" and length > 0) and
  (._trust_summary.datasets_total == $dataset_count) and
  (._trust_summary.by_status | type == "object") and
  ([._trust_summary.by_status[]] | add == $dataset_count) and
  (.datasets | type == "array" and length > 0) and
  ([.datasets[].dataset_id] | length == (unique | length)) and
  all(.datasets[];
    (.dataset_id | type == "string" and length > 0) and
    (.status | type == "string" and length > 0)
  )
' "$health_file" >/dev/null; then
  printf 'Health snapshot is invalid or its derived summary totals do not match its dataset rows\n' >&2
  exit 1
fi
health_count="$(jq -er '.datasets | length' "$health_file")"

manifest_ids="$(jq -r '.datasets[].id' "$manifest_file" | sort)"
health_ids="$(jq -r '.datasets[].dataset_id' "$health_file" | sort)"
if [[ "$manifest_ids" != "$health_ids" ]]; then
  printf 'Manifest and health snapshot dataset IDs do not match\n' >&2
  exit 1
fi

if [[ -f "$agent_root/attestations/latest/index.json" ]]; then
  key_registry="$agent_root/docs/.well-known/datapulse-probe-keys.json"
  index="$agent_root/attestations/latest/index.json"
  head="$agent_root/attestations/latest/chain_head.json"
  scores="$agent_root/attestations/latest/scores.json"
  jq -e --argjson expected "$manifest_count" '.schema == "datapulse/v1/probe-key-registry" and (.keys | length > 0)' "$key_registry" >/dev/null
  jq -e --argjson expected "$manifest_count" '.schema == "datapulse/v1/attestation-index" and (.attestations | length == $expected)' "$index" >/dev/null
  jq -e --argjson expected "$manifest_count" '.schema == "datapulse/v1/daily-chain-head-envelope" and (.dataset_links | length == $expected) and (.chain_head | test("^[0-9a-f]{64}$"))' "$head" >/dev/null
  jq -e --argjson expected "$manifest_count" '.schema == "datapulse/v1/trust-scores" and (.datasets | length == $expected)' "$scores" >/dev/null
  first_ref="$(jq -er '.attestations | to_entries[0].value' "$index")"
  jq -e '.schema == "datapulse/v1/probe-attestation-envelope" and (.payload.key_id | type == "string") and (.chain_link | test("^[0-9a-f]{64}$"))' "$agent_root/$first_ref" >/dev/null
  printf 'Attestation artifacts discoverable: %s signed datasets.\n' "$manifest_count"
fi

checked_at="$(jq -r '.checked_at' "$health_file")"
fresh_count="$(jq '[.datasets[] | select(.status == "fresh")] | length' "$health_file")"

printf '\nAgent-ready verification passed: %s manifest datasets match %s health records.\n' \
  "$manifest_count" "$health_count"
printf 'Health snapshot checked at: %s\n' "$checked_at"
printf 'Fresh datasets (status=fresh): %s/%s\n' "$fresh_count" "$health_count"
jq -r --slurpfile health "$health_file" '
  ($health[0].datasets | map({key: .dataset_id, value: .status}) | from_entries) as $statuses
  | .datasets[]
  | select($statuses[.id] == "fresh")
  | "- \(.name) [\(.id)] — \(.licence)"
' "$manifest_file"

if (( fresh_count < health_count )); then
  printf '\nOther dataset statuses:\n'
  jq -r --slurpfile health "$health_file" '
    ($health[0].datasets | map({key: .dataset_id, value: .status}) | from_entries) as $statuses
    | .datasets[]
    | select($statuses[.id] != "fresh")
    | "- \(.name) [\(.id)] — \($statuses[.id]) — \(.licence)"
  ' "$manifest_file"
fi

printf '\nLicence summary (all %s datasets):\n' "$manifest_count"
jq -r '
  [.datasets[] | .licence]
  | group_by(.)
  | map({licence: .[0], count: length})
  | .[]
  | "- \(.licence): \(.count)"
' "$manifest_file"
