# Datasets & Schema

This page documents the manifest registry and its JSON Schema, the health-report
and JSON-envelope formats, the validation rules every contribution must pass,
and an agency-grouped catalog of all **122 tracked datasets** with representative
schemas and quirks.

## Manifest: `datapulse.json`

`datapulse.json` is the top-level discovery registry. It contains a `datasets`
array of 122 entries; every entry must include exactly these twelve fields (see
`datapulse.schema.json`, JSON Schema 2020-12, `additionalProperties: false`):

- `id` — short, lowercase, hyphen-separated dataset ID; unique and must match
  both the Markdown report and JSON envelope filenames.
- `name` — human-readable dataset name.
- `source` — publishing portal/system (e.g. `data.gov.my`, `ePerolehan`).
- `steward` — responsible government agency.
- `url` — official source URL (must be a valid URI).
- `licence` — licence name stated on the official source.
- `attribution` — required attribution string.
- `refresh_frequency` — expected cadence (free text, e.g. `weekly`, `daily`,
  `daily (weekdays, 0900 MYT)`, `biennial to triennial (survey years)`).
- `expected_record_count` — optional numeric baseline represented as an integer
  or `null` when no stable baseline is declared.
- `geo_coverage` — geographic scope (free text; conventions vary, see below).
- `health_report` — relative path matching `^data/[A-Za-z0-9_-]+\.md$`.
- `namespace` — source category such as `economy`, `weather`, or `transport`.

The `$schema` field at the root must equal the schema's own URL. The schema
enforces `minItems: 1` and a closed per-dataset shape with no optional fields.

### `geo_coverage` conventions

`geo_coverage` is free text and uses inconsistent conventions across datasets:
bare country name (`Malaysia`), annotated scope (`Malaysia (national)`,
`national`), enumerated areas (`Malaysia (13 states + W.P. Kuala Lumpur + W.P.
Labuan + W.P. Putrajaya)`), counted units (`Malaysia (222 parliamentary
constituencies)`, `Malaysia (68 monitoring stations)`), or
`national (BNM reference rates)`. Consumers should treat it as descriptive text,
not a parsed structure.

## Health report: `data/<id>.md`

A human-readable assessment. Reports begin with **YAML frontmatter**
(`dataset_id`, `last_checked`, `status`, `freshness_delta`,
`next_expected_update`, `record_count`, `date_range`, `schema_version`,
`schema_drift`, `known_quirks`, `breaking_changes`, `licence`, `attribution`)
followed by Markdown body sections: Status, Last checked, Coverage, Schema
(field | type | nullable | definition), Known quirks, Breaking changes, Sample
links, Reproducibility commands, and Licence. Reports state observed facts
without implying DataPulse MY is the official publisher.

Notable structural variants:

- `eperolehan-diklankan.md` has **no YAML frontmatter**; it begins directly with
  an H1 and a two-level schema (6 listing fields + 7 detail fields).
- `pricecatcher.md` adds a `file_size_bytes`/`file_count` section for its
  multi-file Parquet bundle.

Status values are constrained to `healthy`, `degraded`, or `unavailable` (the
manifest/validation layer). JSON envelopes additionally use `current` (on-cadence
bulk downloads) and `stale` (freshness exceeds cadence).

## JSON envelope: `data/json/<id>.json`

The machine-readable twin of the health report. Most envelopes carry
`schema: "datapulse/v0.1/dataset-health"` and include at minimum: `id`,
`status`, `freshness_days`, `fields` (with types), `known_quirks`, `licence`,
and `attribution`. Envelopes may also carry `last_checked`,
`next_expected_update`, `record_count` / `row_count`, `date_range`,
`refresh_frequency`, `checks` (named pass/fail observations with method notes),
`breaking_changes`, and a `reproducibility.commands` array. Freshness and row
counts must be non-negative numbers; dates must be ISO 8601 `YYYY-MM-DD`.

There are three structural variants in practice:

- **Structured-checks format (majority, ~86 datasets)** — all `dosm_*`,
  `dgm_*`, `met_weather`, `kkm_idengue`, `exchangerates_*`. A `checks` array of
  named pass/warn observations; a `fields` array with `name`, `type`, `format`,
  `nullable`, `unit`, `constant`, `distinct_values`, `values`, `language`, and
  `description`.
- **Nested-checks format (`fuelprice`)** — uses a `checks` object with
  sub-objects per check type (`freshness`, `schema`, `record_count`), a richer
  `schema_fields` array, and a `dataset_id` key instead of `id`.
- **Camofox / special format (~7 datasets)** — `doe_apims`, `doe_rqims`,
  `doe_mqims`, `eperolehan-diklankan`, `met_weather`, `pricecatcher`,
  `exchangerates_*`. Dataset-specific extensions such as `pricecatcher`'s
  `files` array (role/url/size for main + two lookup Parquets) and
  `eperolehan-diklankan`'s `listing_fields` + `detail_fields` arrays.

Field-level enrichment in JSON that is not in the Markdown reports:
`distinct_values`, enumerated `values`, `constant` (always-same fields such as
`series_type: "level"`), `language: "ms"` (Bahasa Malaysia text fields), and
explicit `unit` values (RM/litre, °C, MLD).

### `next_expected_update` polymorphism

This field holds one of three types depending on context:

- A **date string** (`2026-08-06`) for periodic datasets with a predictable next
  refresh.
- A **cadence string** (`monthly`, `daily`) for open-ended periodic datasets
  where the exact date is not computed.
- **`null`** for the 11 HIES survey datasets (`dosm_hh_*`), whose next survey
  year is unpredictable.

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

The 122 datasets are grouped below by namespace and ID prefix / source agency. Each group lists
the IDs and documents representative schemas and shared quirks; the
authoritative per-dataset schema lives in `data/<id>.md`.

### DOSM — 45 datasets

The largest group. Two stewards appear in the manifest: "DOSM Malaysia" for the
28 OpenDOSM economic/labour/demographic series and "Department of Statistics
Malaysia" for the 17 HIES household-survey series.

IDs:
```
dosm_cpi_state  dosm_cpi_inflation  dosm_cpi_core_inflation  dosm_cpi_state_inflation
dosm_ppi  dosm_ipi_domestic  dosm_ipi_export
dosm_gdp_qtr_real  dosm_gdp_qtr_real_sa  dosm_gdp_qtr_nominal
dosm_gdp_annual_real_supply  dosm_gdp_annual_nominal_supply  dosm_gdp_gni_annual_nominal
dosm_gdp_state_real_supply
dosm_trade_headline  dosm_trade_enduse_bec  dosm_trade_sitc_1d
dosm_lfs_qtr  dosm_lfs_qtr_state  dosm_lfs_year  dosm_lfs_month  dosm_employment_sector
dosm_population_malaysia  dosm_population_state  dosm_population_parlimen
dosm_birth_state  dosm_death_state  dosm_death_district_sex
dosm_death_maternal  dosm_death_maternal_state  dosm_fertility
dosm_marriages_state  dosm_marriages_state_age
dosm_hh_income  dosm_hh_income_state  dosm_hh_income_district
dosm_hh_poverty  dosm_hh_poverty_state  dosm_hh_poverty_district
dosm_hh_inequality  dosm_hh_inequality_state  dosm_hh_inequality_district
dosm_hh_expenditure_dun  dosm_hh_expenditure_parlimen
dosm_crime_district
```

Shared quirks:

- **Annual datasets use January 1** as the date (`YYYY-01-01`).
- **HIES survey datasets (11)** use non-periodic `biennial to triennial (survey
  years)` cadence with `next_expected_update: null`.
- **Aggregate/national rows coexist with state/district rows** in several series
  (CPI state, crime district, trade); filter by the geography column when you
  need a single level.
- **Leading-zero codes must stay strings** (e.g. CPI division codes in
  `dosm_cpi_state`, `dosm_cpi_state_inflation`).
- Licence: Creative Commons Attribution 4.0. Access: direct HTTP (bulk
  Parquet/CSV on `storage.dosm.gov.my`).

### DGM (data.gov.my portal) — 35 datasets

Hosted on `storage.data.gov.my` but stewarded by diverse agencies (BNM, MOH,
EPF, SPAN, KTMB, MCMC, etc.). The `dgm_` prefix denotes the hosting portal, not
a single agency.

IDs:
```
dgm_interest_rates  dgm_interest_rates_annual  dgm_money_aggregates
dgm_currency_in_circulation  dgm_epf_dividend
dgm_payments_systems  dgm_payments_instruments  dgm_payments_channels
dgm_payments_transactions_fpx
dgm_federal_finance_qtr_revenue  dgm_federal_finance_qtr_oe
dgm_state_finance_expenditure
dgm_electricity_consumption  dgm_electricity_supply
dgm_water_consumption  dgm_water_production  dgm_water_access
dgm_hospital_beds  dgm_healthcare_staff  dgm_infant_immunisation
dgm_blood_donations_state  dgm_pekab40_screenings_state  dgm_drug_addicts_age
dgm_prisoners_state  dgm_std_state  dgm_schools_district
dgm_local_authority_sex  dgm_parliament_sex
dgm_vehicle_registrations_type_fuel  dgm_crops_state  dgm_fish_landings
dgm_ktmb_ridership_monthly  dgm_ridership_headline  dgm_mnha
```

Shared quirks:

- Licence: Creative Commons Attribution 4.0. Access: direct HTTP (`curl --head`
  checks `Content-Length` and `Last-Modified`).
- **Nullable fields for newer programs** — e.g. `dgm_ridership_headline` bus/rail
  columns are nullable for services that launched later.
- Some datasets report long freshness deltas (`dgm_water_consumption` ~680 days,
  `dgm_crops_state`) when the steward publishes infrequently.

### BNM — 4 exchange-rate datasets

`exchangerates_daily_0900`, `_1130`, `_1200`, `_1700`. Identical schema and
quirks; they differ only in publication time and endpoint ID.

- **Steward / source:** Bank Negara Malaysia via `data.gov.my`.
- **Cadence:** daily on weekdays at the named MYT time.
- **Coverage:** ~7,000 historical records back to 1997-01-02.
- **Fields:** `date`, `rate_type` (`buying` | `middle` | `selling`), and 27
  ISO-4217 currency columns (`aed`, `aud`, …, `xdr`).
- **Quirks:** each endpoint returns full history back to 1997, not just the
  latest record; `rate_type` varies by row (buying/selling/middle).
- **Reproducibility:**
  ```sh
  curl "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_0900&limit=1"
  ```
- Licence: Open Government Licence (Malaysia).

### DOE — 3 environmental datasets

`doe_apims` (air quality, hourly), `doe_rqims` (river water quality, hourly),
`doe_mqims` (marine water quality, monthly).

- **Access:** Camofox browser rendering — legacy hosts return 403/404; the live
  portals are JavaScript-rendered and need a 10–12s render wait.
- **`doe_apims` quirk:** `**` suffix means multiple pollutants share the dominant
  API index and is stripped in normalized samples.
- Licence: Open Government Licence (Malaysia).

### MOF — 2 datasets

**`fuelprice`** — Malaysian weekly fuel prices.

- **Steward / source:** Ministry of Finance Malaysia via `data.gov.my`.
- **Cadence:** weekly. **Status:** healthy, 0 days behind.
- **Coverage:** 472 weekly rows, 2017-03-30 through 2026-07-30.
- **Fields:** `date`, `rous97`, `ron95`, `diesel`, `diesel_euro5`, `lpg`,
  `kerosene` (numeric except `date`). The JSON envelope is at `schema_version`
  1.1 — the only dataset above 1.0 (subsidy fields were added after launch).
- **Quirks:** the `offset` parameter is silently ignored; the date filter is
  silently ignored. Retrieve the full dataset and paginate/filter locally.

**`eperolehan-diklankan`** — ePerolehan tender notices (DIIKLANKAN).

- **Cadence:** daily. **Access:** JavaScript-rendered, Camofox scrape.
- **Two-level schema:** 6 listing fields (`title`, `agency`, `publish_date`,
  `close_date`, `days_remaining`, `briefing_flag`) + 7 detail fields (`ministry`,
  `estimated_value_rm`, `kod_bidang` (array), `supplier_status`, `coverage_area`,
  `validity_days`, `procurement_method`).
- **Quirks:** `href-dash` links require a click-flow; detail pages render 8–12s
  after a click; gridcell indexes are offset by 1.

### KPDN — `pricecatcher`

Daily grocery prices released as a monthly bulk Parquet bundle.

- **Cadence:** monthly. **Access:** bulk Parquet download only — **not** through
  the data.gov.my OpenAPI.
- **Files:** main `pricecatcher_YYYY-MM.parquet` plus two lookup Parquets
  (`lookup_item.parquet`, `lookup_premise.parquet`). Filename suffix is the
  publish month.
- **Main fields (4):** `date`, `premise_code` (integer FK into `lookup_premise`),
  `item_code` (integer FK into `lookup_item`), `price` (float, RM). Join both
  lookups before presenting or analysing records.
- Licence: Open Government Licence (Malaysia).

### KKM — `kkm_idengue`

Weekly dengue case counts.

- **Access:** Camofox browser rendering. State names are Bahasa Malaysia text
  (`language: "ms"` in the envelope).
- Licence: Open Government Licence (Malaysia).

### MET Malaysia — `met_weather`

Weather forecast.

- **Access:** direct JSON API (not listed in the data.gov.my catalogue).
  Forecast text fields are Bahasa Malaysia.
- Licence: Open Government Licence (Malaysia).

## Adding a new dataset

Follow the "Adopt a dataset" model in `CONTRIBUTING.md`:

1. Open an issue (`.github/ISSUE_TEMPLATE/new-dataset.yml`) describing the
   dataset and its official source.
2. Add the manifest entry to `datapulse.json`.
3. Add `data/<id>.md` (health report) and `data/json/<id>.json` (envelope).
4. Add a small sample under `samples/` (downloaded from the live source; use a
   `# SAMPLE:` flag if hand-constructed — no fabrication).
5. Run the validation checks, reproduce observations against the official
   source, and confirm the licence/attribution.
6. Open a pull request
   (`.github/PULL_REQUEST_TEMPLATE.md`) linking the issue with evidence for
   freshness, schema, and licence claims.
