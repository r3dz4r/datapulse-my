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
    if [[ "$path" == ".well-known/"* ]]; then
      path="docs/$path"
    fi
    if [[ "$path" == "health/latest.json" && -n "${DATAPULSE_LOCAL_HEALTH_FILE:-}" ]]; then
      cp "$DATAPULSE_LOCAL_HEALTH_FILE" "$work_dir/$name"
    else
      cp "$path" "$work_dir/$name"
    fi
    return
  fi
  curl --fail --location --silent --show-error \
    --retry 12 --retry-delay 15 --retry-all-errors \
    --connect-timeout 10 --max-time 30 \
    "$base_url/$path" --output "$work_dir/$name"
}

fetch manifest.json datapulse.json
fetch health.json health/latest.json
fetch trends.json health/trends.json
fetch drift.json health/drift.json
fetch reconciliation.json health/reconciliation.json
fetch catalog.json data/jsonld/catalog.json
fetch catalog-snapshot.json catalog-snapshot.json
fetch catalog-graph.json catalog-graph.json
fetch mcp.json mcp.json
fetch llms.txt llms.txt
fetch attestation-keys.json .well-known/datapulse-probe-keys.json
fetch attestation-index.json attestations/latest/index.json
fetch attestation-head.json attestations/latest/chain_head.json
fetch attestation-scores.json attestations/latest/scores.json

vertical_ids=()
while IFS= read -r dataset_id; do
  [[ -n "$dataset_id" ]] || continue
  vertical_ids+=("$dataset_id")
  fetch "record-evidence-$dataset_id.json" "record-evidence/$dataset_id/latest.json"
done < <(jq -r '.datasets[] | select(.vertical == true) | .id' "$work_dir/manifest.json")

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

from scripts.gen_record_evidence import validate_record_evidence

work = Path(sys.argv[1])
base = sys.argv[2]
manifest = json.loads((work / "manifest.json").read_text())
health = json.loads((work / "health.json").read_text())
trends = json.loads((work / "trends.json").read_text())
drift = json.loads((work / "drift.json").read_text())
reconciliation = json.loads((work / "reconciliation.json").read_text())
attestation_keys = json.loads((work / "attestation-keys.json").read_text())
attestation_index = json.loads((work / "attestation-index.json").read_text())
attestation_head = json.loads((work / "attestation-head.json").read_text())
attestation_scores = json.loads((work / "attestation-scores.json").read_text())
catalog = json.loads((work / "catalog.json").read_text())
catalog_snapshot = json.loads((work / "catalog-snapshot.json").read_text())
catalog_graph = json.loads((work / "catalog-graph.json").read_text())

manifest_ids = [row["id"] for row in manifest["datasets"]]
health_ids = [row["dataset_id"] for row in health["datasets"]]
catalog_ids = [row["identifier"] for row in catalog["dataset"]]
expected_count = len(health_ids)
assert expected_count > 0
assert len(manifest_ids) == len(set(manifest_ids)) == expected_count
assert len(health_ids) == len(set(health_ids)) == expected_count
assert len(catalog_ids) == len(set(catalog_ids)) == expected_count
assert set(manifest_ids) == set(health_ids) == set(catalog_ids)
assert attestation_keys["schema"] == "datapulse/v1/probe-key-registry"
assert attestation_index["schema"] == "datapulse/v1/attestation-index"
assert len(attestation_index["attestations"]) == expected_count
assert attestation_head["schema"] == "datapulse/v1/daily-chain-head-envelope"
assert len(attestation_head["dataset_links"]) == expected_count
assert re.fullmatch(r"[0-9a-f]{64}", attestation_head["chain_head"])
assert attestation_scores["schema"] == "datapulse/v1/trust-scores"
assert len(attestation_scores["datasets"]) == expected_count
assert attestation_scores["methodology_version"] == 3
reasons = {"measured", "classified", "insufficient_history", "not_applicable", "missing_record", "unknown_status"}
for row in attestation_scores["datasets"]:
    assert row["methodology_version"] == 3
    assert set(row["component_availability"]) == set(row["components"])
    for state in row["component_availability"].values():
        assert isinstance(state.get("available"), bool)
        assert state.get("reason") in reasons
        assert state["available"] == (state["reason"] in {"measured", "classified"})

trend_ids = [row["dataset_id"] for row in trends["datasets"]]
assert trends["schema"] == "datapulse/v1/dataset-trends"
assert len(trend_ids) == len(set(trend_ids)) == expected_count
assert set(trend_ids) == set(manifest_ids)
assert trends["summary"]["datasets_total"] == expected_count
assert set(trends["summary"]["by_trend"]) == {
    "deteriorating", "recovering", "stable", "insufficient_data"
}
assert sum(trends["summary"]["by_trend"].values()) == expected_count
assert set(trends["summary"]["by_reliability_grade"]) == {
    "A", "B", "C", "D", "F", "insufficient_data"
}
assert sum(trends["summary"]["by_reliability_grade"].values()) == expected_count
assert all(row["trend"] in trends["summary"]["by_trend"] for row in trends["datasets"])
assert all(
    row["reliability_grade"] in trends["summary"]["by_reliability_grade"]
    for row in trends["datasets"]
)

drift_ids = [row["dataset_id"] for row in drift["datasets"]]
assert drift["schema"] == "datapulse/v1/dataset-drift"
assert len(drift_ids) == len(set(drift_ids)) == expected_count
assert set(drift_ids) == set(manifest_ids)
assert drift["summary"]["datasets_total"] == expected_count
assert set(drift["summary"]["by_verdict"]) == {
    "drift_detected", "record_count_drift", "stable", "insufficient_data"
}
assert sum(drift["summary"]["by_verdict"].values()) == expected_count
assert all(row["verdict"] in drift["summary"]["by_verdict"] for row in drift["datasets"])
assert all(
    row["record_count_within_tolerance"] is None
    or isinstance(row["record_count_within_tolerance"], bool)
    for row in drift["datasets"]
)

assert reconciliation["schema"] == "datapulse/v1/dataset-reconciliation"
assert isinstance(reconciliation["groups"], list)
assert reconciliation["summary"]["datasets_total"] == expected_count
assert reconciliation["summary"]["groups_total"] == len(reconciliation["groups"])
assert reconciliation["summary"]["datasets_grouped"] + reconciliation["summary"]["datasets_single_source"] == expected_count
assert set(reconciliation["summary"]["by_verdict"]) == {"agree", "discrepancy", "different_granularity", "insufficient_data"}
assert sum(reconciliation["summary"]["by_verdict"].values()) == reconciliation["summary"]["groups_total"]
grouped_ids = [member["id"] for group in reconciliation["groups"] for member in group["members"]]
assert len(grouped_ids) == len(set(grouped_ids))
assert set(grouped_ids) <= set(manifest_ids)
assert len(grouped_ids) == reconciliation["summary"]["datasets_grouped"]
assert all(group["verdict"] in reconciliation["summary"]["by_verdict"] for group in reconciliation["groups"])

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

edge_kinds = (
    "same_steward",
    "same_agency",
    "same_geography",
    "canonical_series",
    "successor_to",
    "shared_schema",
)
weights = {
    "same_steward": 2,
    "same_agency": 1,
    "same_geography": 1,
    "canonical_series": 2,
    "successor_to": 3,
    "shared_schema": 1,
}
assert set(catalog_graph) >= {
    "generated_at", "node_count", "edge_count", "edge_kinds", "coverage",
    "precision", "nodes", "edges",
}
nodes = catalog_graph["nodes"]
edges = catalog_graph["edges"]
assert isinstance(nodes, list) and isinstance(edges, list)
assert catalog_graph["generated_at"] == health["checked_at"]
assert catalog_graph["node_count"] == len(manifest_ids) == len(nodes)
assert [node["dataset_id"] for node in nodes] == sorted(manifest_ids)
assert all(
    isinstance(node, dict)
    and set(node) == {"dataset_id", "title", "steward", "agency"}
    and isinstance(node["dataset_id"], str)
    and isinstance(node["title"], str)
    for node in nodes
)
assert set(catalog_graph["edge_kinds"]) == set(edge_kinds)
assert all(
    isinstance(count, int) and not isinstance(count, bool) and count >= 0
    for count in catalog_graph["edge_kinds"].values()
)
assert catalog_graph["edge_count"] == len(edges) == sum(catalog_graph["edge_kinds"].values())
edge_keys = [(edge["kind"], edge["from"], edge["to"]) for edge in edges]
assert edge_keys == sorted(edge_keys)
assert len(edge_keys) == len(set(edge_keys))
assert all(
    isinstance(edge, dict)
    and set(edge) == {"kind", "from", "to", "weight", "provenance"}
    and edge["kind"] in edge_kinds
    and edge["from"] in set(manifest_ids)
    and edge["to"] in set(manifest_ids)
    and edge["from"] != edge["to"]
    and edge["weight"] == weights[edge["kind"]]
    and isinstance(edge["provenance"], dict)
    and set(edge["provenance"]) == {"matched_fields", "manifest_version"}
    and isinstance(edge["provenance"]["matched_fields"], list)
    and edge["provenance"]["matched_fields"]
    and all(isinstance(field, str) and field for field in edge["provenance"]["matched_fields"])
    and edge["provenance"]["manifest_version"] == manifest["$schema"]
    for edge in edges
)
connected = {endpoint for edge in edges for endpoint in (edge["from"], edge["to"])}
assert catalog_graph["coverage"] == {
    "datasets_with_at_least_one_edge": len(connected),
    "isolated_datasets": sorted(set(manifest_ids) - connected),
}
assert catalog_graph["precision"]["measured"] is False
assert catalog_graph["precision"]["fuzzy_edges"] == 0

verticals = [row for row in manifest["datasets"] if row.get("vertical") is True]
for dataset in verticals:
    dataset_id = dataset["id"]
    path = work / f"record-evidence-{dataset_id}.json"
    record_evidence = json.loads(path.read_text(encoding="utf-8"))
    assert dataset.get("record_evidence_schema") == "record-evidence/v1"
    assert record_evidence["dataset_id"] == dataset_id
    assert record_evidence["source_url"] == dataset.get("record_source_url", dataset["url"])
    errors = validate_record_evidence(record_evidence, full=False)
    assert not errors, f"{path}: {'; '.join(errors)}"
    excerpt_count = len(record_evidence["records"])
    if record_evidence["record_count"]:
        assert 1 <= excerpt_count <= 100
    else:
        assert excerpt_count == 0

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

PYTHONPATH=mcp python3 - "$work_dir/mcp.json" "$work_dir/llms.txt" <<'PY'
import asyncio
import json
import re
import sys

import server


async def main() -> None:
    advertised_document = json.load(open(sys.argv[1], encoding="utf-8"))
    advertised_tools = advertised_document["tools"]
    runtime_tools = await server.mcp.list_tools()
    expected_tools = [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.parameters,
            **(
                {"annotations": tool.annotations.model_dump(exclude_none=True)}
                if getattr(tool, "annotations", None) is not None
                else {}
            ),
        }
        for tool in runtime_tools
    ]
    assert advertised_tools == expected_tools
    llms = open(sys.argv[2], encoding="utf-8").read()
    blocks = re.findall(
        r"<!-- BEGIN mcp-tools -->\n(.*?)\n<!-- END mcp-tools -->",
        llms,
        flags=re.DOTALL,
    )
    assert len(blocks) == 1, "llms.txt must contain exactly one MCP tools block"
    documented_tools = re.findall(r"^\| `([a-z][a-z0-9_]*)\(", blocks[0], re.MULTILINE)
    runtime_names = [tool.name for tool in runtime_tools]
    assert documented_tools == runtime_names

    advertised_resources = [resource["uri"] for resource in advertised_document["resources"]]
    runtime_resources = await server.mcp.list_resources()
    runtime_templates = await server.mcp.list_resource_templates()
    expected_resources = [str(resource.uri) for resource in runtime_resources]
    expected_resources.extend(template.uri_template for template in runtime_templates)
    assert advertised_resources == expected_resources
    assert len(runtime_resources) == 8
    assert len(runtime_templates) == 1
    print(
        "MCP runtime schema assertion: PASS "
        f"({len(runtime_tools)} tools, {len(runtime_resources)} concrete resources, "
        f"{len(runtime_templates)} template)"
    )


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

if [[ -z "${DATAPULSE_API_KEYS_FILE:-}" ]]; then
  printf 'Buyer API keys: WARN (DATAPULSE_API_KEYS_FILE is unset; key validation skipped)\n' >&2
else
  python3 - "$DATAPULSE_API_KEYS_FILE" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    document = json.load(source)
active = document.get("active", [])
assert isinstance(active, list), "buyer API active keys must be an array"
for index, key in enumerate(active):
    assert isinstance(key, dict), f"active key {index} must be an object"
    assert isinstance(key.get("hashed_token"), str) and key["hashed_token"], f"active key {index} has no hashed_token"
    scopes = key.get("scopes")
    assert isinstance(scopes, list) and scopes and all(isinstance(s, str) and re.fullmatch(r"[a-z]+(?:\.[a-z]+)+", s) for s in scopes), f"active key {index} has invalid scopes"
print(f"Buyer API keys: PASS ({len(active)} active)")
PY
fi

expected_methodology_title="$(sed -n 's/^# //p' docs/health-methodology.md | head -n 1)"
[[ -n "$expected_methodology_title" ]] || {
  printf 'Health methodology: source title is missing\n' >&2
  exit 1
}
if $local_mode; then
  methodology_file="docs/health-methodology.html"
else
  methodology_file="$work_dir/health-methodology.html"
  fetch "health-methodology.html" "health-methodology.html"
fi
[[ -s "$methodology_file" ]] || {
  printf 'Health methodology: rendered HTML is missing or empty\n' >&2
  exit 1
}
grep -Fq ">$expected_methodology_title<" "$methodology_file" || {
  printf 'Health methodology: rendered HTML does not contain source title\n' >&2
  exit 1
}
printf 'Health methodology HTML: PASS\n'
