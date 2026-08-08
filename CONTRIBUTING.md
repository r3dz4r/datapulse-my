# Contributing to DataPulse MY

Thank you for helping make Malaysian public data easier to assess and reuse.

## Adopt or update a dataset

Each manifest dataset has these published artifacts:

1. `data/<id>.md` — human-readable health and provenance report.
2. `data/jsonld/<id>.json` — schema.org JSON-LD metadata.
3. `data/json/<id>.json` — machine-readable report envelope for the 136
   non-GTFS datasets (every non-GTFS manifest ID).

The 30 GTFS datasets are the current exception to the third artifact: they
have Markdown reports, JSON-LD, and files under `samples/gtfs-static/` or
`samples/gtfs-realtime/`, but no `data/json/<id>.json` envelope. Do not invent
an envelope only to satisfy a filename convention. GTFS datasets remain
excluded by `scripts/contract-scope.json:json_envelope.excluded_ids` (the 30
GTFS IDs).

Use a stable lowercase ID made from letters, numbers, hyphens, or underscores.
It must match the manifest `id`, report filename, JSON-LD filename, and any
non-GTFS JSON-envelope filename.

## Manifest contract

Every `datapulse.json` row requires:

- `id`, `name`, `source`, `steward`, and official `url`;
- `licence` and `attribution`;
- `refresh_frequency`, `expected_record_count`, and `geo_coverage`;
- `health_report` and `namespace`.

The lifecycle fields are `real_status` (`live` or `discontinued`),
`verified_at`, optional `probe_note`, and optional `discontinued_reason`.
Use one of the namespaces declared in `datapulse.schema.json`. Keep
`expected_record_count` as a non-negative integer or `null` when no defensible
expectation exists.

## Health reports and status

Reports should distinguish source reachability, content freshness, record
count, schema/shape observations, access method, licence, attribution, and
known collection quirks. DataPulse MY is an observer, not the authoritative
publisher.

The eight health statuses are:

- `fresh` — reachable, structurally usable, and within its freshness window;
- `aging` — beyond 1.5× cadence but no more than 3× cadence;
- `stale` — beyond 3× cadence;
- `degraded` — reachable but content, count, or schema checks failed;
- `browser-dependent` — reliable assessment requires a rendered browser;
- `unreachable` — the source request failed or returned a terminal HTTP error;
- `unknown` — no usable health classification is available;
- `unknown-freshness` — reachable and structurally usable, but without a
  Last-Modified header or parseable content date.

## Generated artifacts

Do not hand-edit `health/latest.json`, files under `badges/` or `data/jsonld/`,
`feed.xml`, the README trust summary, `changelog.json`, or the dashboard graph.
Run their generators after source changes:

```sh
bash scripts/check.sh > health/latest.json
bash scripts/gen_badges.sh
bash scripts/gen_rss.sh
bash scripts/gen_readme_summary.sh
python3 scripts/gen_changelog.py
python3 scripts/gen_jsonld_catalog.py
```

Individual JSON-LD files, the catalog, and the dashboard graph are generated
from the manifest and current health state. Regenerate them when adding a
dataset; never patch their output by hand.

## Validate before submitting

Create an isolated development environment and install the runtime plus test
dependencies from the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

The runtime dependency files remain `requirements.txt` for repository scripts
and `mcp/requirements.txt` for the MCP service. `requirements-dev.txt` composes
those files with the packages used only by tests and local invariant checks.

```sh
python3 -m jsonschema -i datapulse.json datapulse.schema.json
python3 -m pytest -q mcp/tests
python3 -m json.tool data/json/<id>.json >/dev/null  # non-GTFS only
python3 -m json.tool data/jsonld/<id>.json >/dev/null
bash scripts/verify_agent_ready.sh
```

Also confirm that IDs are unique, referenced files exist, dates use ISO 8601,
URLs resolve, licence evidence comes from the official publisher, and no
credentials, cookies, personal data, or copied source records are committed.

## Submit a pull request

1. Open an issue describing the dataset, official source, licence, and expected
   cadence.
2. Create a focused branch and update the manifest plus applicable artifacts.
3. Run the generators and validation commands above.
4. Open a pull request that links the issue and states when and how the source
   was checked.

Reviewers may request a repeat observation for dynamic, intermittent, or
JavaScript-rendered sources.
