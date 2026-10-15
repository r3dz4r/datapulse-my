# Discovery jurisdiction ranking decision — 2026-10-16

Board card: `t_259ab13f`. Evidence baseline: `d5b6460bac` on
`session/dp-rank-jurisdiction`. Decision/design only; no runtime change.

## Question

Should `search_datasets`, when neither `source` nor `licence` is supplied,
prefer Malaysian-source candidates given its Malaysian public-data positioning?
Yes, with preference strength tied to query intent: prioritize Malaysia for
explicitly Malaysian requests, use jurisdiction only to break equal scores for
neutral requests, and preserve the existing order for explicitly Singapore-scoped
requests. Singapore catalogue membership is deliberate; removing those datasets
is not part of this decision. The question is ordering, not trust verification.

## Ranking code path

The implementation is [mcp/server.py](../mcp/server.py):
`search_datasets` (lines 1268–1347) loads manifest/health through
`_load_catalogue` (1089–1091), applies filters, computes `_search_score`
(1247–1258), sorts candidates, then slices to `limit` (default 10, API maximum
50). These are the ordering authorities, rather than `mcp.json`.

Exact scoring lines, `mcp/server.py:1247–1258`:

```python
def _search_score(entry: dict[str, Any], query: str) -> int:
    """Score query terms with title weighted above an optional description."""
    title = entry.get("name", "").casefold()
    description = entry.get("description", "").casefold()
    normalised_query = " ".join(query.casefold().split())
    terms = re.findall(r"[a-z0-9]+", normalised_query)
    score = sum(5 * title.count(term) + description.count(term) for term in terms)
    if normalised_query == " ".join(title.split()):
        score += 100
    elif normalised_query and normalised_query in title:
        score += 15
    return score
```

Exact eligibility lines, `mcp/server.py:1315–1326`:

```python
    requested_licence = _canonical_licence(licence) if licence else None
    requested_source = source.casefold().strip() if source else None
    matches: list[dict[str, Any]] = []

    for entry in manifest.get("datasets", []):
        if requested_licence and entry.get("licence", "").casefold() != requested_licence.casefold():
            continue
        if requested_source and requested_source not in entry.get("source", "").casefold():
            continue
        score = _search_score(entry, query)
        if score == 0:
            continue
```

Exact final ordering, `mcp/server.py:1339–1347`:

```python
    matches.sort(
        key=lambda item: (
            -item["score"],
            0 if item["id"].startswith("gtfs_static_") else 1,
            item["title"],
            item["id"],
        )
    )
    return matches[:limit]
```

The rank uses **one lexical score, no jurisdiction term**, followed by an
explicit static-GTFS ID tie-break, case-sensitive title order, then ID order.
Title means manifest `name`. Optional `description` would contribute at weight
1, but all 440 current entries lack a nonempty description. Terms match
substrings, not words; repeat occurrences and repeated query terms accumulate.
The +100 exact-title and +15 whole-query-substring bonuses are mutually exclusive.

`source` and `licence` affect eligibility only: source is a case-insensitive
substring; licence uses canonical aliases such as `CC BY 4.0`, then exact
case-insensitive equality. `namespace`, `geo_coverage`, custodian and steward do
not feed the score or sort. Health `status` is returned from the snapshot
(default `unknown`), but neither filters nor boosts rank. There is no
freshness/reliability boost.

The local public-facing claim is visible in `SEARCH_DESCRIPTION`
(`mcp/server.py:684–685`: “Malaysian public datasets”), the tool title
(`mcp/server.py:1262`: “Find Malaysian Public Data”), and MCP instructions
(`mcp/server.py:849–850`: “official Malaysian public datasets”).
`mcp.json` repeats the Malaysian description and pins the inflation query in
`tools[name=search_datasets].inputSchema.properties.query.examples`.
The instructions currently say 425, while the manifest/search description say
440; that separate count inconsistency is observed, not repaired here.

## Reproduction

Run from `/home/redza/.worktrees/wt-dp-rank-jurisdiction`. This calls this tree's
actual async handler directly, as supported by the installed FastMCP version.
Only `_load_catalogue` is replaced in memory with the two local JSON files.
It bypasses middleware, so no usage ledger is written. Network connects are
disabled, and `PYTHONDONTWRITEBYTECODE` prevents bytecode writes. No test suite,
generator, live endpoint or upstream is invoked.

The three displayed requests use valid API limits. For blast-radius analysis
only, the direct Python call asks for all 440 possible candidates; it bypasses
the API's limit validation deliberately. The inflation prefix is checked against
a valid limit-50 call. Variant results are **counterfactual in-memory sorts**,
not deployed behaviour. Scores, candidates, status and within-group tie-breaks
remain unchanged.

Exact command run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 - <<'PY'
import asyncio
import hashlib
import json
import re
import socket
import sys
from pathlib import Path

def offline(*args, **kwargs):
    raise AssertionError("network disabled for offline reproduction")

socket.socket.connect = offline
socket.socket.connect_ex = offline
root = Path.cwd()
sys.path.insert(0, str(root / "mcp"))
import server

manifest = json.loads(Path("datapulse.json").read_text())
health = json.loads(Path("health/latest.json").read_text())
entries = manifest["datasets"]
by_id = {d["id"]: d for d in entries}

async def local_catalogue():
    return manifest, health

server._load_catalogue = local_catalogue

def emit(label, value):
    print(label, json.dumps(value, ensure_ascii=False, sort_keys=True))

def sg(row):
    return "data.gov.sg" in row["source"].casefold()

def base_key(row):
    return (-row["score"], 0 if row["id"].startswith("gtfs_static_") else 1,
            row["title"], row["id"])

def variant(rows, query, kind, source=None, licence=None):
    if source is not None or licence is not None:
        return rows
    if kind == "scoped" and {"sg", "singapore"} & set(re.findall(r"[a-z0-9]+", query.casefold())):
        return rows
    if kind == "tie" or (kind == "scoped" and not {"malaysia", "malaysian"} & set(re.findall(r"[a-z0-9]+", query.casefold()))):
        key = lambda r: (-r["score"], sg(r), *base_key(r)[1:])
    elif kind == "primary":
        key = lambda r: (sg(r), *base_key(r))
    else:
        q = " ".join(query.casefold().split())
        key = lambda r: (q != " ".join(r["title"].casefold().split()),
                         sg(r), *base_key(r))
    return sorted(rows, key=key)

def changes(old, new):
    a, b = [r["id"] for r in old], [r["id"] for r in new]
    return {"moved_all": sum(x != y for x, y in zip(a, b)),
            "moved_top10": sum(x != y for x, y in zip(a[:10], b[:10])),
            "added_top10": len(set(b[:10]) - set(a[:10])),
            "top1_changed": a[:1] != b[:1]}

async def rows_for(query):
    # The direct Python handler bypasses schema limits: 440 is only for
    # analytical full-candidate comparison, not a valid MCP request limit.
    return await server.search_datasets(query=query, limit=len(entries))

async def main():
    for path in ("mcp/server.py", "datapulse.json", "health/latest.json", "mcp.json"):
        emit("sha256", {path: hashlib.sha256(Path(path).read_bytes()).hexdigest()})
    foreign = [d for d in entries if sg(d)]
    emit("catalogue", {"total": len(entries), "data.gov.sg": len(foreign),
         "sg_ids": [d["id"] for d in foreign],
         "sg_geo_coverage": sorted({d.get("geo_coverage", "") for d in foreign}),
         "with_description": sum(bool(d.get("description")) for d in entries)})
    query = "Malaysian public data inflation"
    for extra in ({"limit": 3}, {"source": "OpenDOSM", "limit": 10},
                  {"licence": "CC BY 4.0", "limit": 3}):
        emit("request", {"query": query, **extra})
        emit("result", await server.search_datasets(query=query, **extra))
    rows = await rows_for(query)
    emit("pinned_candidates", len(rows))
    for kind in ("tie", "primary", "scoped"):
        changed = variant(rows, query, kind)
        emit(kind, {**changes(rows, changed),
             "top10": [[r["id"], r["score"]] for r in changed[:10]]})
    # Check that schema-valid prefixes agree with the analytical full list.
    assert rows[:50] == await server.search_datasets(query=query, limit=50)
    for name, queries in (
        ("existing_search_queries", ["labour state", "Malaysian Fuel Prices",
                                    "Fuel Prices", "ktmb", "fuel", "fuel prices"]),
        ("sg_exact_titles", [d["name"] for d in foreign]),
        ("sg_topic_controls", ["Singapore weather", "SG taxi", "HDB resale prices"]),
        ("unique_catalogue_titles", sorted({d["name"] for d in entries})),
    ):
        emit("corpus", {"name": name, "queries": len(queries),
                        "unique_queries": len(set(queries))})
        totals = {k: {"queries_changed": 0, "top1_changed": 0, "moved_all": 0,
                     "moved_top10": 0, "added_top10": 0}
                  for k in ("tie", "primary", "scoped")}
        for q in queries:
            old = await rows_for(q)
            for kind, total in totals.items():
                new = variant(old, q, kind)
                delta = changes(old, new)
                total["queries_changed"] += bool(delta["moved_all"])
                for key in delta:
                    total[key] += delta[key]
                if name == "sg_topic_controls" and kind == "scoped":
                    emit("sg_topic_control", {"query": q, "variant": kind,
                         "before": old[0]["id"] if old else None,
                         "after": new[0]["id"] if new else None,
                         **delta})
        emit("corpus_metrics", totals)
    hdb = by_id["sg_datagov_hdb_metadata"]
    emit("hdb_term_scores", {t: 5 * hdb["name"].casefold().count(t)
         for t in re.findall(r"[a-z0-9]+", query.casefold())})
    for extra in ({"source": "OpenDOSM"}, {"licence": "CC BY 4.0"}):
        filtered = await server.search_datasets(query=query, limit=50, **extra)
        for kind in ("tie", "primary", "scoped"):
            assert variant(filtered, query, kind, **extra) == filtered
        emit("filter_guard", {"filter": extra, "candidates": len(filtered),
                              "all_variants_identical": True})

asyncio.run(main())
PY
```

Pasted stdout (exit 0):

```text
sha256 {"mcp/server.py": "b8c76798f39db4de5029e6fcc6b0036e8d7d658e4fda58f23662d113709116fd"}
sha256 {"datapulse.json": "fb1acd8edeb10d7d45ee8ac846ed544a4f091009ddb0721f6b345cf053af702f"}
sha256 {"health/latest.json": "ad694fefa1c04da8e4584a3d156dc276151c925df1d84b30075c6606b57ae8d1"}
sha256 {"mcp.json": "917cafb1bc6375d5bc79357fd09c83bc32a02f1e3cbeb1fb49b875a8809e6a2f"}
catalogue {"data.gov.sg": 5, "sg_geo_coverage": ["Singapore"], "sg_ids": ["sg_datagov_coe_bidding", "sg_datagov_hdb_resale_prices", "sg_datagov_hdb_metadata", "sg_datagov_taxi_availability", "sg_datagov_weather_readings"], "total": 440, "with_description": 0}
request {"limit": 3, "query": "Malaysian public data inflation"}
result [{"id": "sg_datagov_hdb_metadata", "licence": "Singapore Open Data Licence v1.0 (attribution required)", "score": 10, "source": "data.gov.sg", "status": "fresh", "title": "HDB Dataset Metadata (SG)"}, {"id": "datasets", "licence": "Open Government Licence (Malaysia)", "score": 10, "source": "data.gov.my (OpenAPI)", "status": "aging", "title": "List of Datasets on data.gov.my"}, {"id": "metrics_content", "licence": "Open Government Licence (Malaysia)", "score": 10, "source": "data.gov.my (OpenAPI)", "status": "fresh", "title": "Number of Datasets on data.gov.my"}]
request {"limit": 10, "query": "Malaysian public data inflation", "source": "OpenDOSM"}
result [{"id": "cpi_core_inflation", "licence": "Creative Commons Attribution 4.0", "score": 5, "source": "OpenDOSM (also indexed by data.gov.my)", "status": "fresh", "title": "Monthly Core CPI Inflation"}, {"id": "dosm_cpi_inflation", "licence": "Creative Commons Attribution 4.0", "score": 5, "source": "OpenDOSM (storage.dosm.gov.my)", "status": "fresh", "title": "OpenDOSM Monthly CPI Inflation by Division"}, {"id": "dosm_cpi_state_inflation", "licence": "Creative Commons Attribution 4.0", "score": 5, "source": "OpenDOSM (storage.dosm.gov.my)", "status": "fresh", "title": "OpenDOSM Monthly CPI Inflation by State and Division"}, {"id": "dosm_cpi_core_inflation", "licence": "Creative Commons Attribution 4.0", "score": 5, "source": "OpenDOSM (storage.dosm.gov.my)", "status": "fresh", "title": "OpenDOSM Monthly Core CPI Inflation by Division"}]
request {"licence": "CC BY 4.0", "limit": 3, "query": "Malaysian public data inflation"}
result [{"id": "ridership_headline", "licence": "Creative Commons Attribution 4.0", "score": 10, "source": "data.gov.my (storage.data.gov.my)", "status": "stale", "title": "data.gov.my Daily Public Transport Ridership"}, {"id": "schools_district", "licence": "Creative Commons Attribution 4.0", "score": 10, "source": "data.gov.my (storage.data.gov.my)", "status": "fresh", "title": "data.gov.my Public Education Institutions by District"}, {"id": "dosm_cpi_annual_inflation", "licence": "Creative Commons Attribution 4.0", "score": 5, "source": "DOSM via data.gov.my", "status": "aging", "title": "Annual CPI Inflation by Division (2-digit)"}]
pinned_candidates 51
tie {"added_top10": 0, "moved_all": 5, "moved_top10": 5, "top10": [["datasets", 10], ["metrics_content", 10], ["ridership_headline", 10], ["schools_district", 10], ["sg_datagov_hdb_metadata", 10], ["dosm_cpi_annual_inflation", 5], ["metrics_dataset_cumul", 5], ["usage_metrics", 5], ["lecturers_uni", 5], ["economic_indicators", 5]], "top1_changed": true}
primary {"added_top10": 1, "moved_all": 51, "moved_top10": 10, "top10": [["datasets", 10], ["metrics_content", 10], ["ridership_headline", 10], ["schools_district", 10], ["dosm_cpi_annual_inflation", 5], ["metrics_dataset_cumul", 5], ["usage_metrics", 5], ["lecturers_uni", 5], ["economic_indicators", 5], ["fuelprice", 5]], "top1_changed": true}
scoped {"added_top10": 1, "moved_all": 51, "moved_top10": 10, "top10": [["datasets", 10], ["metrics_content", 10], ["ridership_headline", 10], ["schools_district", 10], ["dosm_cpi_annual_inflation", 5], ["metrics_dataset_cumul", 5], ["usage_metrics", 5], ["lecturers_uni", 5], ["economic_indicators", 5], ["fuelprice", 5]], "top1_changed": true}
corpus {"name": "existing_search_queries", "queries": 6, "unique_queries": 6}
corpus_metrics {"primary": {"added_top10": 0, "moved_all": 16, "moved_top10": 16, "queries_changed": 3, "top1_changed": 0}, "scoped": {"added_top10": 0, "moved_all": 16, "moved_top10": 16, "queries_changed": 3, "top1_changed": 0}, "tie": {"added_top10": 0, "moved_all": 16, "moved_top10": 16, "queries_changed": 3, "top1_changed": 0}}
corpus {"name": "sg_exact_titles", "queries": 5, "unique_queries": 5}
corpus_metrics {"primary": {"added_top10": 7, "moved_all": 102, "moved_top10": 37, "queries_changed": 4, "top1_changed": 4}, "scoped": {"added_top10": 0, "moved_all": 0, "moved_top10": 0, "queries_changed": 0, "top1_changed": 0}, "tie": {"added_top10": 1, "moved_all": 51, "moved_top10": 12, "queries_changed": 4, "top1_changed": 0}}
corpus {"name": "sg_topic_controls", "queries": 3, "unique_queries": 3}
sg_topic_control {"added_top10": 0, "after": "mbpp_weather_stations", "before": "mbpp_weather_stations", "moved_all": 0, "moved_top10": 0, "query": "Singapore weather", "top1_changed": false, "variant": "scoped"}
sg_topic_control {"added_top10": 0, "after": "sg_datagov_taxi_availability", "before": "sg_datagov_taxi_availability", "moved_all": 0, "moved_top10": 0, "query": "SG taxi", "top1_changed": false, "variant": "scoped"}
sg_topic_control {"added_top10": 0, "after": "sg_datagov_hdb_resale_prices", "before": "sg_datagov_hdb_resale_prices", "moved_all": 3, "moved_top10": 3, "query": "HDB resale prices", "top1_changed": false, "variant": "scoped"}
corpus_metrics {"primary": {"added_top10": 0, "moved_all": 4, "moved_top10": 4, "queries_changed": 1, "top1_changed": 1}, "scoped": {"added_top10": 0, "moved_all": 3, "moved_top10": 3, "queries_changed": 1, "top1_changed": 0}, "tie": {"added_top10": 0, "moved_all": 3, "moved_top10": 3, "queries_changed": 1, "top1_changed": 0}}
corpus {"name": "unique_catalogue_titles", "queries": 434, "unique_queries": 434}
corpus_metrics {"primary": {"added_top10": 12, "moved_all": 10408, "moved_top10": 75, "queries_changed": 107, "top1_changed": 4}, "scoped": {"added_top10": 3, "moved_all": 5761, "moved_top10": 35, "queries_changed": 103, "top1_changed": 0}, "tie": {"added_top10": 4, "moved_all": 5812, "moved_top10": 47, "queries_changed": 107, "top1_changed": 0}}
hdb_term_scores {"data": 10, "inflation": 0, "malaysian": 0, "public": 0}
filter_guard {"all_variants_identical": true, "candidates": 4, "filter": {"source": "OpenDOSM"}}
filter_guard {"all_variants_identical": true, "candidates": 38, "filter": {"licence": "CC BY 4.0"}}

```

The default order is HDB metadata, catalogue list, catalogue count, all score 10.
OpenDOSM returns the four CPI entries at score 5 in the displayed order.
The licence-filtered prefix contains Malaysian transport/education and then CPI.
The default's HDB score comes entirely from “data” appearing in both “Dataset”
and “Metadata”; it matches neither inflation nor Malaysian scope. Alphabetical
title order places HDB ahead of the tied Malaysian entries.

The supplied earlier live observation reported HDB **score 20**. This run
reproduces **the first dataset and the source-filtered CPI order**, but measures
HDB **score 10**. The difference is unresolved; do not describe these as identical
deployments or infer a live version from the fallback source marker.

## Blast radius

**Catalogue exposure:** `sum("data.gov.sg" in d["source"].casefold() for d in
manifest["datasets"])` gives **5 / 440 = 1.14%**. All five also declare
`geo_coverage: Singapore`; their literal IDs appear in the output.
The other 435 are the Malaysian-side comparison group for this measurement.
This is the requested source-based classification, not an independent
jurisdiction audit of every dataset. The source labels were inspected; no
third-country source classification is asserted.

**Variants measured**, only for absent `source` AND absent `licence`:

- `tie`: sort by lexical score descending, then Malaysian-side before SG,
  then the existing GTFS/title/ID tie-breaks.
- `primary`: put every positive Malaysian-side match ahead of every SG match,
  then apply the entire existing sort. No query-intent exception.
- `scoped` (recommended): explicit whole ASCII tokens `sg` or `singapore`
  preserve the old order, including mixed MY/SG requests. Otherwise, queries
  containing `malaysia` or `malaysian` sort by normalized exact-title match
  first, Malaysian-side second, then the existing sort. Neutral queries use
  `tie`. Exact-title normalization is casefold plus whitespace collapse.
  With either filter supplied, all variants preserve the current filtered order.

These are source preferences among existing positive matches; they neither
manufacture zero-score Malaysian candidates nor exclude SG candidates. The
binary SG/non-SG classifier is a measurement proxy for this snapshot. A later
implementation must define unknown/new-source handling rather than silently
equate every future non-SG source with Malaysia.

For the pinned inflation query there are **51 positive matches**: all 51 change
position under `primary` or `scoped`; all 10 default visible positions change.
HDB moves from rank 1 to rank 51, and `fuelprice` enters the top 10. The top 3
become `datasets`, `metrics_content`, `ridership_headline`. Under `tie`,
only 5 positions change, HDB becomes fifth, and top-10 membership is unchanged.
Thus Malaysian-first fixes the jurisdiction tension but **does not make CPI
the top answer**. Generic “public data” still dominates topic relevance.

Counts below compare IDs at each rank. “All positions” sums changed
query/rank positions across full candidate lists, not unique datasets.
“Top-10 additions” sums newly included IDs per query; each addition also
displaces one old ID. Corpora overlap and must not be added together.

| Corpus | Variant | Queries with any rank change | Top-1 changes | All positions | Top-10 positions | Top-10 additions |
|---|---|---:|---:|---:|---:|---:|
| 434 unique titles from all 440 entries | tie | 107 | 0 | 5,812 | 47 | 4 |
| Same 434 titles | primary | 107 | 4 | 10,408 | 75 | 12 |
| Same 434 titles | scoped | 103 | 0 | 5,761 | 35 | 3 |
| 6 existing test query strings | tie / primary / scoped (each) | 3 | 0 | 16 | 16 | 0 |
| 5 Singapore exact titles | tie | 4 | 0 | 51 | 12 | 1 |
| Same 5 Singapore titles | primary | 4 | 4 | 102 | 37 | 7 |
| Same 5 Singapore titles | scoped | 0 | 0 | 0 | 0 | 0 |
| 3 SG topic controls | scoped | 1 | 0 | 3 | 3 | 0 |

The six existing strings are `labour state`, `Malaysian Fuel Prices`,
`Fuel Prices`, `ktmb`, `fuel`, and `fuel prices`. The `Fuel Prices` and
`fuel prices` variants differ only in case and retain the literal test inputs.
Controls are `Singapore weather`, `SG taxi`, and `HDB resale prices`.
Blanket `primary` changes the last control's top result from
`sg_datagov_hdb_resale_prices` to `fuelprice`; `scoped` preserves HDB first.
`Singapore weather` already returns Malaysian `mbpp_weather_stations` first;
the SG-intent exception preserves that existing weakness rather than claiming
to solve Singapore semantic retrieval.

The filtered guard checks compare whole returned lists under all three
counterfactuals: 4 OpenDOSM inflation candidates and 38 CC BY inflation
candidates remain identical. This is a property of the proposed filter bypass,
not evidence that the production ranker has changed.

**Existing assertions and fixtures, read but not executed:**

| Location / test | Existing contract | Consequence for a later ranking change |
|---|---|---|
| `mcp/tests/test_server.py::test_prioritized_tool_metadata_routes_agents_without_overclaiming` (174; query at 194) | Exact “Malaysian public data inflation” example; generated metadata parity | Keep example and schema unchanged; add an outcome regression for its unfiltered ranking. Current assertion checks metadata, not returned order. |
| `mcp/tests/test_server.py::test_tool_schemas_are_agent_ready` (528; examples at 568–579) | Same query; source examples OpenDOSM/data.gov.my/MET Malaysia and licence aliases | No expected-value change needed for a sort-only implementation. Exercise these filter examples separately; examples are not existing order fixtures. |
| `mcp/tests/test_server.py::test_search_datasets_returns_ranked_live_results` (716) | Combined OpenDOSM + CC BY `labour state` results, descending scores, output keys | Retain unchanged: filtered order and schema remain unchanged. This does not require every unfiltered result to be globally score-sorted. |
| `mcp/tests/test_server.py::test_search_datasets_exact_title_scores_above_partial` (1459) | Exact “Malaysian Fuel Prices” has greater fuelprice score than partial “Fuel Prices”; exact result is first | Retain lexical scores and top result; include both queries in focused future checks. |
| `mcp/tests/test_server.py::test_search_datasets_transport_namespace` (2543) | Local manifest query `ktmb` returns `gtfs_static_ktmb` first | Preserve static-GTFS tie-break; retain assertion. Namespace itself does not score. |
| `mcp/tests/test_mcp_three_call_path.py::test_search_then_verify_returns_complete_fuelprice_answer` (22) | Fixture query “fuel prices” returns fuelprice first before verification | Retain fixture and first-hit assertion. It does not pin SG/MY ordering on the full catalogue. |
| `mcp.json`, search tool query/source/licence examples | Pinned advertised input values, not result snapshots | Check actual results for these inputs; no advertisement edits proposed. |
| `scripts/tests/fixtures/generator/python_release/mcp/server.py`; `scripts/tests/fixtures/ai_catalog/search_datasets.json` | Frozen generator source and discovery-card identity, respectively | Neither pins this catalogue's SG-first result. Do not rewrite fixtures merely to change production ranking; any future generator-output change needs its own reviewed scope. |
| `mcp/tests/fixtures/agent_task_cases.json` | Workflow/citation expectations around fuelprice, not search-result arrays | No fixture-order update identified. |

Searches across `mcp/tests` and `scripts/tests` found no assertion pinning
`sg_datagov_hdb_metadata` first for the inflation query. Its other test mentions
are freshness-extraction checks, unrelated to rank. Future implementation needs
new offline ranking regressions for the pinned query, explicit SG and mixed
intent, neutral high-relevance SG queries, exact titles, positive-match-only
behaviour, filter bypass, and GTFS ties. Existing expectations need not be
weakened. The corpus measurement is not a passing test-suite claim.

## Options

| Option | Cost | Blast radius | What it breaks or leaves unresolved |
|---|---|---|---|
| A. Keep rank; rely on source/licence filters | No server change; callers must know publisher/licence values | 0 ranking changes | Leaves the measured Malaysian-query default failure and claim/behaviour tension. A licence is not a jurisdiction selector, and OpenDOSM covers only part of Malaysia. |
| B. Require explicit jurisdiction filtering before making a Malaysian-scoped claim | Caller contract/validation and a defined cross-source jurisdiction selector; potentially a new parameter in a separate approved design | All unfiltered discovery callers would need adaptation or qualification; not quantifiable from this tree | Breaks the advertised no-filter example workflow if enforced as mandatory. Existing source filtering alone cannot select all Malaysian publishers. Not recommended within this dispatch's unchanged-schema boundary. |
| C1. Malaysian source tie-break only | Small sort change; source classification and regression tests | Pinned query: 5 moved positions; title corpus: 47 top-10 positions, no top-1 changes | Fixes this tree's equal-score HDB case, but cannot reliably fix an SG score strictly above MY, as may be the supplied score-20 live case. |
| C2. Fixed additive Malaysian boost | Choose/calibrate a weight, retain or redefine score meaning, test broader query lengths | Not simulated; impact depends on weight and arbitrary substring counts | A small boost may not cross the gap; a large one can bury relevant SG results or distort exact-title preference. No measured universal safe weight. |
| C3. Blanket Malaysian-first grouping | Simple jurisdiction sort before relevance | Pinned: 51 moved positions; 4/5 SG exact-title top hits displaced; 75 title-corpus top-10 positions | Breaks intentional SG discovery, including “HDB resale prices” becoming fuelprice. **Do not choose this.** |
| D. Scoped Malaysian preference (recommended) | Intent-token branch plus a source tie-break/priority key and focused tests; no schema, description, catalogue or dependency change | Pinned: 51 moved positions; 35 top-10 positions across 434 title queries; no title top-1 changes; filtered lists unchanged | Explicit-MY queries cease being globally lexical-score sorted; limited English intent tokens miss other phrasings. Preserves existing SG-query retrieval weaknesses. |

Option B is a decision alternative only, not a proposal to edit the interface,
advertisement or tool descriptions in this dispatch. No option changes catalogue
membership, trust status taxonomy or upstream state.

## Recommendation

**Choose D: make the unfiltered rank prefer Malaysian sources, strongly for
explicit Malaysian intent and only at equal lexical scores for neutral queries,
while preserving explicit Singapore/mixed-intent and filtered ordering.**
Use the precisely defined `scoped` branch above as the implementation candidate;
this dispatch approves no runtime change.

This treats the Malaysian-query failure as a default-ranking defect relative
to the public scope claim, without treating Singapore membership as a defect.
It handles a higher-scoring SG distractor on the explicit-MY query, whereas a
tie-break alone only happens to fix this snapshot. Keeping lexical precedence
for neutral queries avoids the measured HDB-to-fuelprice regression.

The cost is a small server ordering change plus source classification,
intent handling and the new regression cases named above. Measured impact is
51 reordered candidates for the pinned query and 35 top-10 positions across
the title corpus, with no top-1 title regressions in that corpus. Returned
`score` would still mean lexical score, so explicit-MY results can be ordered
across differing scores by jurisdiction. No numerical boost needs tuning.

**Falsifier:** a reviewed set of genuine neutral discovery requests shows a
loss of intended first-choice datasets from the tie-break, or explicit-MY
requests systematically need SG evidence ahead of relevant Malaysian matches
(for example, a confirmed cross-country comparison use case). That would
invalidate the locale-preference assumption and favour relevance-first
ordering with explicit scope. Independently, any implementation that fails the
measured pinned-query outcome, changes a filtered list, or displaces one of
the five SG exact-title top hits fails this candidate's acceptance contract.
No usage distribution or user relevance labels were available here.

This decision fixes jurisdiction preference only. It does not establish that
the catalogue-list top hit is a good inflation answer; CPI topic relevance
remains a separate measured limitation, not additional implementation scope.

## Evidence boundary

- **Read in code:** scoring, substring matching, bonuses, filters, GTFS/title/ID
  ties, limit slicing, local Malaysian descriptions/instructions, example
  metadata, and the named test/fixture assertions. The September reconciliation
  note records operator-directed Singapore expansion; it does not itself prove
  every subsequent promotion decision.
- **Measured in this run:** local 440-entry catalogue and 5 data.gov.sg sources;
  their Singapore geo coverage; zero nonempty descriptions; the unfiltered,
  source-filtered and licence-filtered handler results; three counterfactual
  ranking variants; corpus counts and filter identity checks. The command
  records SHA-256s of all four relevant input/code files. The title corpus has
  434 distinct strings; it is exhaustive over titles, not possible user queries.
- **Inferred/design judgment:** Malaysian positioning warrants a locale
  preference, an explicit intent branch is safer than blanket grouping, and
  the scoped candidate balances that promise against SG discovery. Non-SG is
  used as the Malaysian-side proxy for measurement; a durable source policy
  still needs an explicit unknown/new-source rule in a later implementation.
- **Not established:** why the supplied live score was 20 instead of local 10;
  the currently deployed code/catalogue identity or served state; all external
  descriptions; actual query frequencies, user relevance judgments, non-English
  intent, exhaustive source jurisdiction, or effects of future catalogue
  changes. No network call, deployment check, full test suite or benchmark of
  real user success was run. Preserving “Singapore weather” preserves an
  existing MY-first result, so the SG exception is not a claim of SG relevance.
- **Change boundary:** only this note is written and committed. No code, tests,
  fixtures, generated artefacts, descriptions, catalogue, taxonomy or other
  worktree is changed; no push, tag, PR or external publication is performed.
