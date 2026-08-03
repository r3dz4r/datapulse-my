# DataPulse MY — OpenWiki Quickstart

DataPulse MY is an open-source **trust layer for Malaysian public data**. It
does not republish official datasets. Instead, for each of the **92 tracked
datasets** across eight Malaysian government agencies, it publishes a set of
artifacts that together let journalists, researchers, civic technologists, and
AI agents assess whether a source is usable and how to handle its quirks:

1. A **manifest entry** in [`datapulse.json`](../datapulse.json) — discovery
   metadata (ID, source, steward, URL, licence, refresh frequency,
   geo-coverage, health-report path). Validated against
   [`datapulse.schema.json`](../datapulse.schema.json) (JSON Schema 2020-12).
2. A **human-readable health report** at `data/<id>.md` — plain-language status,
   freshness, schema, quirks, licence, and reproducibility commands.
3. A **machine-readable health envelope** at `data/json/<id>.json` — the same
   facts in JSON for automated pipelines (status, `freshness_days`, `fields`,
   `known_quirks`, `checks`, reproducibility commands).
4. A **small sample** under `samples/` — 1–5 rows in CSV and/or JSON so
   consumers can inspect the shape without a full download.

On top of these per-dataset artifacts, the project publishes three aggregate
layers:

- **`health/latest.json`** — a weekly machine-readable freshness snapshot of all
  92 datasets, produced by [`scripts/check.sh`](../scripts/check.sh).
- **Status badges** (`badges/<id>.svg`) and an **RSS feed** (`feed.xml`) generated
  from the health snapshot.
- A **single-page dashboard** (`docs/index.html`) and an **AI-agent discovery
  index** ([`llms.txt`](../llms.txt)) that let humans and agents enter the
  catalogue in one fetch.

DataPulse MY is **not the official publisher**. It documents what is available,
whether it is fresh, how the schema behaves, and which collection quirks
consumers need to handle. Source datasets remain subject to their own licences
and attribution requirements. The repository's MIT licence covers its own
original work only.

## What is tracked

92 datasets across eight agencies, grouped by the ID prefix used in the manifest
and the underlying source portal:

| Prefix / group | Agencies | Count | Notes |
| --- | --- | --- | --- |
| `dosm_*` | Department of Statistics Malaysia (DOSM / OpenDOSM) | 45 | Largest group: economic, labour, demographic, household-survey (HIES), trade, CPI, population, vital statistics. |
| `dgm_*` | data.gov.my portal (stewarded by BNM, MOH, EPF, SPAN, KTMB, MCMC, …) | 35 | Bulk files hosted on `storage.data.gov.my`; prefix denotes the hosting portal, not a single agency. |
| `exchangerates_daily_*` | Bank Negara Malaysia (BNM) | 4 | Daily reference rates at four fixed MYT times (0900, 1130, 1200, 1700); identical schema. |
| `doe_*` | Department of Environment (DOE) | 3 | Air (APIMS, hourly), river water (RQIMS, hourly), marine water (MQIMS, monthly). |
| `fuelprice`, `eperolehan-diklankan` | Ministry of Finance (MOF) | 2 | Weekly fuel prices; daily ePerolehan tender notices. |
| `pricecatcher` | KPDN | 1 | Monthly bulk Parquet grocery-price release with two lookup files. |
| `kkm_idengue` | Ministry of Health (KKM) | 1 | Weekly dengue case counts. |
| `met_weather` | MET Malaysia | 1 | Weather forecast (not listed in the data.gov.my catalogue). |

See [Datasets & schema](datasets.md) for the manifest schema, envelope formats,
validation rules, and an agency-grouped catalog with representative schemas and
quirks.

### Licence split

- **Creative Commons Attribution 4.0** — 80 datasets (all `dosm_*` and `dgm_*`,
  hosted on OpenDOSM / `storage.data.gov.my`).
- **Open Government Licence (Malaysia)** — 12 datasets (fuelprice,
  ePerolehan, pricecatcher, the four BNM exchange-rate endpoints, met_weather,
  the three DOE series, kkm_idengue).

### Access-method bifurcation

- **Direct HTTP** (`curl` GET/HEAD) — 85 datasets: bulk Parquet/CSV downloads
  and JSON APIs.
- **Camofox browser rendering** — 7 datasets: `doe_apims`, `doe_rqims`,
  `doe_mqims`, `kkm_idengue`, `eperolehan-diklankan`, plus others requiring
  JavaScript-rendered portals. These need a 10–12s render wait and an
  accessibility-snapshot capture.

## How to use it

### For humans

Start at the dashboard (`https://r3dz4r.github.io/datapulse-my/`) or
[`datapulse.json`](../datapulse.json). Each manifest entry links to a
`data/<id>.md` health report for a plain-language assessment, and the matching
`data/json/<id>.json` envelope for an automated pipeline. Health badges in the
README give a one-glance status.

### For AI agents

Fetch [`llms.txt`](../llms.txt) — the single AI-agent discovery index. It lists
the MCP connection details, the manifest URL, the health-snapshot URL, and every
dataset health report. Alternatively, connect to the read-only MCP server at
`https://mcp.data-pulse.my/mcp` (see [MCP server](mcp.md)). Run
[`scripts/verify_agent_ready.sh`](../scripts/verify_agent_ready.sh) to self-test
that the published artifacts are consistent end-to-end before relying on them.

### For contributors

See [Operations & contribution](operations.md) for the three-file contribution
model, the PR checklist, the scheduled CI pipelines, and how auto-managed agent
marker files are handled.

## Where to go next

- [Datasets & schema](datasets.md) — manifest schema, health-report and
  JSON-envelope formats, the validation rules, and an agency-grouped catalog of
  all 92 datasets with representative schemas and quirks.
- [Operations & contribution](operations.md) — the weekly health-check CI
  pipeline, GitHub Pages deploy, the OpenWiki refresh workflow, the
  three-file contribution model, the PR checklist, and agent marker files.
- [MCP server](mcp.md) — the read-only FastMCP server (tools, resources,
  local run, tests) and the production deployment stack (systemd / nginx /
  Cloudflare Tunnel).

## Key source references

- `README.md` — project purpose, audience, dataset links, and badge embeds.
- `datapulse.json` — the canonical dataset registry; add new datasets here first.
- `datapulse.schema.json` — JSON Schema 2020-12 that validates the manifest.
- `CONTRIBUTING.md` — the three-file contribution model and validation rules.
- `CHANGELOG.md` — release notes; `[Unreleased]` tracks pending outreach.
- `data/<id>.md` and `data/json/<id>.json` — one health report + one envelope
  per dataset.
- `health/latest.json` — the weekly aggregate freshness snapshot.
- `llms.txt` — AI-agent discovery index (one file → full portfolio).
- `scripts/check.sh`, `scripts/gen_badges.sh`, `scripts/gen_rss.sh`,
  `scripts/verify_agent_ready.sh` — health probe and derived-artifact generators.
- `.github/workflows/health-check.yml`, `deploy-pages.yml`,
  `openwiki-update.yml` — the three scheduled CI pipelines.
- `mcp/server.py` — the read-only MCP server.

## Backlog

- **Per-dataset deep-dive pages** — source anchor: `data/*.md` +
  `data/json/*.json`. Deferred: the agency-grouped catalog in `datasets.md`
  captures representative schemas and quirks; promote individual pages only when
  a dataset accumulates enough distinct collection/quirk detail to justify it.
- **Full per-dataset schema tables in the wiki** — the authoritative field-level
  schema for each dataset already lives in its `data/<id>.md` report; duplicating
  all 92 here would be unmaintainable.
- **GitHub Pages dashboard internals** — source anchor: `docs/index.html`. The
  dashboard is a static page with embedded data injected at deploy time; it has
  no runtime API surface worth a dedicated page yet.
