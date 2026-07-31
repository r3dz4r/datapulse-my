# Datasets & Schema

This page documents the manifest registry, the health-report and JSON-envelope
formats, the validation rules every contribution must pass, and a catalog of all
seven tracked datasets with their key schemas and quirks.

## Manifest: `datapulse.json`

`datapulse.json` is the top-level discovery registry. It contains a `datasets`
array; every entry must include these fields (see `CONTRIBUTING.md`):

- `id` — short, lowercase, hyphen-separated dataset ID; must be unique and match
  both the Markdown report and JSON envelope filenames.
- `name` — human-readable dataset name.
- `source` — publishing portal/system (e.g. `data.gov.my`, `ePerolehan`).
- `steward` — responsible government agency.
- `url` — official source URL.
- `licence` — licence name stated on the official source.
- `attribution` — required attribution string.
- `refresh_frequency` — expected cadence (e.g. `weekly`, `daily`, `monthly`,
  or `daily (weekdays, 0900 MYT)`).
- `geo_coverage` — geographic scope (e.g. `Malaysia`, `national`).
- `health_report` — relative path to the Markdown report (`data/<id>.md`).

## Health report: `data/<id>.md`

A human-readable assessment. Reports may include YAML frontmatter
(`dataset_id`, `last_checked`, `status`, `freshness_delta`,
`next_expected_update`, schema metadata, `known_quirks`, `breaking_changes`,
`licence`, `attribution`) followed by Markdown body sections covering status,
freshness, coverage, schema, known quirks, breaking changes, reproducibility
commands, and licence. Reports state observed facts without implying DataPulse
MY is the official publisher.

Status values are constrained to `healthy`, `degraded`, or `unavailable`.

## JSON envelope: `data/json/<id>.json`

The machine-readable twin of the health report. At minimum it includes the
dataset `id`, `status`, `freshness_days`, `fields` (with types), `known_quirks`,
`licence`, and `attribution`. Envelopes may also carry `last_checked`,
`next_expected_update`, `record_count` / `row_count`, `date_range`,
`refresh_frequency`, `checks` (named pass/fail observations with method notes),
`breaking_changes`, and a `reproducibility.commands` array. Freshness and row
counts must be non-negative numbers; dates must be ISO 8601 `YYYY-MM-DD`.

## Validation rules

Before submitting a dataset contribution (`CONTRIBUTING.md`):

- `datapulse.json` and the envelope must parse as JSON.
- The dataset ID must be unique and match both report filenames.
- Use ISO 8601 `YYYY-MM-DD` dates; freshness and row counts as non-negative
  numbers.
- Status must be `healthy`, `degraded`, or `unavailable`.
- Every manifest `health_report` path must exist.
- The Markdown report and JSON envelope must be factually consistent.
- No credentials, cookies, personal data, or copied source records.
- Check links and reproduce observations against the official source.

PowerShell validation snippet from `CONTRIBUTING.md`:

```powershell
Get-Content -Raw datapulse.json | ConvertFrom-Json | Out-Null
Get-Content -Raw data/json/<dataset-id>.json | ConvertFrom-Json | Out-Null
```

## Dataset catalog

### `fuelprice` — Malaysian Fuel Prices

- **Steward / source:** Ministry of Finance Malaysia via `data.gov.my`.
- **Cadence:** weekly. **Status:** healthy, 0 days behind.
- **Coverage:** 472 weekly rows, 2017-03-30 through 2026-07-30.
- **Fields:** `date`, `rous97`, `ron95`, `diesel`, `diesel_euro5`, `lpg`,
  `kerosene` (all numeric except `date`).
- **Quirks:** the `offset` parameter is silently ignored; the date filter is
  silently ignored. Retrieve the full dataset and paginate/filter locally.
- **Sources:** `data/fuelprice.md`, `data/json/fuelprice.json`.

### `eperolehan-diklankan` — ePerolehan Tender Notices (DIIKLANKAN)

- **Steward / source:** MOF / ePerolehan.
- **Cadence:** daily. **Status:** healthy, 0 days. **Access:** JavaScript-rendered,
  scraped via Camofox (a browser-capable workflow is required).
- **Listing fields (6):** `title`, `agency`, `publish_date`, `close_date`,
  `days_remaining`, `briefing_flag`.
- **Detail fields (7):** `ministry`, `estimated_value_rm`, `kod_bidang` (array),
  `supplier_status`, `coverage_area`, `validity_days`, `procurement_method`.
- **Quirks:** `href-dash` links require a click-flow rather than direct
  navigation; detail pages render 8–12 seconds after a click; gridcell indexes
  are offset by 1.
- **Sources:** `data/eperolehan-diklankan.md`, `data/json/eperolehan-diklankan.json`.

### `pricecatcher` — PriceCatcher (Daily Grocery Prices)

- **Steward / source:** KPDN via `data.gov.my`.
- **Cadence:** monthly. **Status:** healthy, 0 days. **Access:** bulk Parquet
  download only — **not** available through the data.gov.my OpenAPI.
- **Files:** main `pricecatcher_YYYY-MM.parquet` plus two lookup Parquets
  (`lookup_item.parquet`, `lookup_premise.parquet`). Filename suffix is the
  publish month.
- **Main fields (4):** `date` (`YYYY-MM-DD`), `premise_code` (integer FK into
  `lookup_premise`), `item_code` (integer FK into `lookup_item`), `price`
  (float, RM).
- **Lookups:** item lookup maps `item_code` to name/unit/category; premise
  lookup maps `premise_code` to name/address/district/state. Join both lookups
  before presenting or analysing records.
- **Sources:** `data/pricecatcher.md`, `data/json/pricecatcher.json`.

### BNM Daily Exchange Rates — `exchangerates_daily_0900`, `_1130`, `_1200`, `_1700`

These four datasets share an identical schema and quirks; they differ only in
publication time and endpoint ID.

- **Steward / source:** Bank Negara Malaysia via `data.gov.my`.
- **Cadence:** daily on weekdays at the named MYT time (0900, 1130, 1200, 1700).
- **Status:** healthy, 0 days. **Coverage:** ~7,000 historical records,
  1997-01-02 through 2026-07-31. BNM reference rates published in Kuala Lumpur.
- **Fields:** `date` (`YYYY-MM-DD`), `rate_type` (`buying` | `middle` |
  `selling`), and 27 ISO-4217 currency columns: `aed`, `aud`, `bnd`, `cad`,
  `chf`, `cny`, `egp`, `eur`, `gbp`, `hkd`, `idr`, `inr`, `jpy`, `khr`, `krw`,
  `mmk`, `npr`, `nzd`, `php`, `pkr`, `sar`, `sgd`, `thb`, `twd`, `usd`, `vnd`,
  `xdr`.
- **Quirks:** four daily endpoints at fixed MYT times; each endpoint returns
  full history back to 1997 (not just the latest record); `rate_type` varies by
  row — a bank sells foreign currency at the buying rate, buys it at the selling
  rate, and the middle rate is their average.
- **Reproducibility:**
  ```sh
  curl "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_0900&limit=1"
  ```
- **Sources:** `data/exchangerates_daily_{0900,1130,1200,1700}.md` and the
  matching files under `data/json/`.

## Adding a new dataset

Follow the "Adopt a dataset" model in `CONTRIBUTING.md`:

1. Open an issue describing the dataset and its official source.
2. Add the manifest entry to `datapulse.json`.
3. Add `data/<id>.md` (health report) and `data/json/<id>.json` (envelope).
4. Run the validation checks, reproduce observations against the official
   source, and confirm the licence/attribution.
5. Open a pull request linking the issue with evidence for freshness, schema,
   and licence claims.
