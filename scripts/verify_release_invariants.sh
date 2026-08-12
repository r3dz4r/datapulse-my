#!/usr/bin/env bash
set -Eeuo pipefail

local_mode=false
if [[ "${1:-}" == "--local" ]]; then
  local_mode=true
  shift
fi
if (( $# > 0 )); then
  printf 'Usage: %s [--local]\n' "$0" >&2
  exit 2
fi

base_url="${DATAPULSE_RELEASE_BASE_URL:-https://data-pulse.my}"
base_url="${base_url%/}"
canonical_base_url="${DATAPULSE_CANONICAL_BASE_URL:-https://data-pulse.my}"
canonical_base_url="${canonical_base_url%/}"

for command in curl jq python3; do
  command -v "$command" >/dev/null 2>&1 || {
    printf 'Required command not found: %s\n' "$command" >&2
    exit 1
  }
done

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

fetch() {
  local name="$1" path="$2"
  if $local_mode; then
    if [[ "$path" == "health/latest.json" && -n "${DATAPULSE_LOCAL_HEALTH_FILE:-}" ]]; then
      cp "$DATAPULSE_LOCAL_HEALTH_FILE" "$work_dir/$name"
    else
      cp "$path" "$work_dir/$name"
    fi
    return
  fi
  curl --fail --location --silent --show-error --retry 2 \
    --connect-timeout 10 --max-time 30 \
    "$base_url/$path" --output "$work_dir/$name"
}

fetch manifest.json datapulse.json
fetch health.json health/latest.json
fetch catalog.json data/jsonld/catalog.json
fetch catalog-snapshot.json catalog-snapshot.json
fetch mcp.json mcp.json
fetch llms.txt llms.txt

dataset_count="$(
  jq -er '.datasets | select(type == "array" and length > 0) | length' \
    "$work_dir/health.json"
)"

python3 -m jsonschema -i "$work_dir/manifest.json" datapulse.schema.json

python3 - "$work_dir" "$canonical_base_url" <<'PY'
import json
import re
import sys
from collections import Counter
from pathlib import Path

work = Path(sys.argv[1])
base = sys.argv[2]
manifest = json.loads((work / "manifest.json").read_text())
health = json.loads((work / "health.json").read_text())
catalog = json.loads((work / "catalog.json").read_text())
catalog_snapshot = json.loads((work / "catalog-snapshot.json").read_text())

manifest_ids = [row["id"] for row in manifest["datasets"]]
health_ids = [row["dataset_id"] for row in health["datasets"]]
catalog_ids = [row["identifier"] for row in catalog["dataset"]]
expected_count = len(health_ids)
assert expected_count > 0
assert len(manifest_ids) == len(set(manifest_ids)) == expected_count
assert len(health_ids) == len(set(health_ids)) == expected_count
assert len(catalog_ids) == len(set(catalog_ids)) == expected_count
assert set(manifest_ids) == set(health_ids) == set(catalog_ids)

missing_reports = [
    dataset_id for dataset_id in health_ids
    if not (Path("data") / f"{dataset_id}.md").is_file()
]
assert not missing_reports, f"missing dataset reports: {', '.join(missing_reports)}"

missing_jsonld = [
    dataset_id for dataset_id in manifest_ids
    if not (Path("data/jsonld") / f"{dataset_id}.json").is_file()
]
assert not missing_jsonld, f"missing per-dataset JSON-LD: {', '.join(missing_jsonld)}"

for row in catalog["dataset"]:
    report_url = f"{base}/data/{row['identifier']}.md"
    assert row["url"] == report_url
    assert row["distribution"][0]["contentUrl"] == report_url

summary = health["_trust_summary"]
actual_statuses = Counter(row["status"] for row in health["datasets"])
summary_statuses = {
    key.replace("_", "-"): value for key, value in summary["by_status"].items()
}
assert sum(summary_statuses.values()) == expected_count
assert summary_statuses == {status: actual_statuses[status] for status in summary_statuses}

readme = Path("README.md").read_text(encoding="utf-8")
line = next(
    line for line in readme.splitlines()
    if line.startswith("Current distribution (`_trust_summary`):")
)
readme_statuses = {
    label: int(count) for count, label in re.findall(r"\[(\d+) ([^]]+)\]", line)
}
assert readme_statuses == {
    status: count for status, count in summary_statuses.items() if count
}

assert catalog_snapshot["generated_at"] == health["checked_at"]
assert catalog_snapshot["health"]["checked_at"] == health["checked_at"]
assert catalog_snapshot["manifest"]["datasets_total"] == expected_count
assert catalog_snapshot["health"]["datasets_total"] == expected_count
assert catalog_snapshot["health"]["by_status"] == summary_statuses
assert len(catalog_snapshot["datasets"]) == expected_count

with (work / "artifact-urls.txt").open("w", encoding="utf-8") as output:
    for dataset_id in manifest_ids:
        print(f"{base}/data/jsonld/{dataset_id}.json", file=output)
    for row in catalog["dataset"]:
        print(row["url"], file=output)

llms = (work / "llms.txt").read_text(encoding="utf-8")
urls = sorted(set(re.findall(r"https://[^\s<>()\[\]`\"']+", llms)))
if not urls:
    raise AssertionError("llms.txt contains no absolute HTTPS URLs")
with (work / "llms-urls.txt").open("w", encoding="utf-8") as output:
    output.write("\n".join(url.rstrip(".,;:") for url in urls) + "\n")

print(f"release metadata assertions: PASS ({expected_count} datasets)")
PY

PYTHONPATH=mcp python3 - "$work_dir/mcp.json" <<'PY'
import asyncio
import json
import sys

import server


async def main() -> None:
    advertised = json.load(open(sys.argv[1], encoding="utf-8"))["tools"]
    runtime = await server.mcp.list_tools()
    expected = [
        {"name": tool.name, "description": tool.description, "inputSchema": tool.parameters}
        for tool in runtime
    ]
    assert advertised == expected
    print("MCP runtime schema assertion: PASS (5 tools)")


asyncio.run(main())
PY

check_url_file() {
  local label="$1" url_file="$2"
  local attempt=0 failures=""
  # Retry the whole batch up to 3 times with backoff. GH Pages CDN
  # propagation can momentarily 5xx right after a deploy; a transient
  # 502/503 on any URL should not fail the release.
  while (( attempt < 3 )); do
    if failures="$(xargs -r -n1 -P12 bash -c '
      url="$1"
      code="$(curl --location --silent --show-error --retry 2 \
        --connect-timeout 10 --max-time 30 --output /dev/null \
        --write-out "%{http_code}" "$url")" || exit 1
      case "$code" in
        2??|3??|400|401|403|405|406|415) ;;
        *) printf "%s %s\n" "$code" "$url" >&2; exit 1 ;;
      esac
    ' _ < "$url_file")"; then
      printf '%s URLs: PASS (%s checked)\n' "$label" "$(wc -l < "$url_file")"
      return 0
    fi
    attempt=$((attempt + 1))
    if (( attempt < 3 )); then
      printf '%s URL validation transient failure (attempt %s/3), retrying...\n' "$label" "$attempt" >&2
      sleep 5
    fi
  done
  printf '%s URL validation failed\n' "$label" >&2
  printf '%s\n' "$failures" >&2
  exit 1
}

if $local_mode; then
  printf 'Local JSON-LD/report files: PASS (%s checked)\n' "$dataset_count"
  printf 'Local llms.txt format: PASS\n'
else
  check_url_file "JSON-LD/report" "$work_dir/artifact-urls.txt"
  check_url_file "llms.txt" "$work_dir/llms-urls.txt"
fi

printf 'Post-deploy release invariants: PASS\n'
