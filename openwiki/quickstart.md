# DataPulse MY — OpenWiki Quickstart

DataPulse MY is an open-source **trust layer for Malaysian public data**. It
does not republish official datasets. Instead, for each tracked dataset it
publishes three artifacts that together let journalists, researchers, civic
technologists, and developers assess whether a source is usable and how to
handle its quirks:

1. A **manifest entry** in `datapulse.json` — discovery metadata (ID, source,
   steward, URL, licence, refresh frequency, health-report path).
2. A **human-readable health report** at `data/<id>.md` — plain-language status,
   freshness, schema, quirks, licence, and reproducibility commands.
3. A **machine-readable health envelope** at `data/json/<id>.json` — the same
   facts in valid JSON for automated pipelines (status, `freshness_days`,
   fields, `known_quirks`, `checks`, reproducibility commands).

DataPulse MY is **not the official publisher**. It documents what is available,
whether it is fresh, how the schema behaves, and which collection quirks
consumers need to handle. Source datasets remain subject to their own licences
and attribution requirements.

## What is tracked

Seven datasets across three Malaysian government agencies:

| Dataset ID | Steward | Cadence | Access |
| --- | --- | --- | --- |
| `fuelprice` | MOF (Ministry of Finance) | weekly | data.gov.my OpenAPI |
| `eperolehan-diklankan` | MOF / ePerolehan | daily | JavaScript-rendered, Camofox scrape |
| `pricecatcher` | KPDN | monthly | bulk Parquet download |
| `exchangerates_daily_0900` | BNM | daily (weekday, 0900 MYT) | data.gov.my OpenAPI |
| `exchangerates_daily_1130` | BNM | daily (weekday, 1130 MYT) | data.gov.my OpenAPI |
| `exchangerates_daily_1200` | BNM | daily (weekday, 1200 MYT) | data.gov.my OpenAPI |
| `exchangerates_daily_1700` | BNM | daily (weekday, 1700 MYT) | data.gov.my OpenAPI |

All seven share the same manifest schema, health-report format, and JSON
envelope shape. The four BNM exchange-rate datasets differ only in publication
time and endpoint ID; their schema and quirks are identical.

## How to use it

Start with [`datapulse.json`](../datapulse.json) to discover datasets and their
official sources. Follow each `health_report` link for a plain-language
assessment, or consume the matching file under `data/json/` in an automated
workflow. For example, a pipeline can inspect `status` and `freshness_days`
before processing a source, while a researcher can review known quirks before
designing a collection method.

## Where to go next

- [Datasets & schema](datasets.md) — manifest fields, health-report and
  JSON-envelope formats, the full dataset catalog with schemas and quirks, and
  the validation rules every contribution must pass.
- [Operations & contribution](operations.md) — the scheduled OpenWiki CI
  workflow, the three-file contribution model, the PR checklist, and how
  auto-managed agent marker files are handled.

## Key source references

- `README.md` — project purpose, audience, and dataset links.
- `datapulse.json` — the canonical dataset registry; add new datasets here first.
- `CONTRIBUTING.md` — the three-file contribution model and validation rules.
- `CHANGELOG.md` — release notes; `[Unreleased]` tracks pending outreach.
- `data/<id>.md` and `data/json/<id>.json` — one health report + one envelope
  per dataset.
- `.github/workflows/openwiki-update.yml` — daily scheduled OpenWiki refresh.

## Backlog

- **Per-dataset deep-dive pages** — source anchor: `data/*.md` + `data/json/*.json`.
  Deferred: the catalog table in `datasets.md` currently captures the essential
  schema and quirks for all seven datasets; promote individual pages only when a
  dataset accumulates enough distinct collection/quirk detail to justify it.
- **Automated freshness/health CI checks** — source anchor: `CONTRIBUTING.md`
  validation rules. Deferred: validation is currently manual (PowerShell JSON
  parse + link/freshness checks); no automated CI gate exists yet.
