---
dataset_id: dgm_interest_rates_annual
last_checked: 2026-08-02T17:18:27Z
status: current
freshness_delta: 119 days since file update
next_expected_update: annual
record_count: 707
date_range: 1980-01-01 to 2025-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Annual values are averages of the underlying rate observations.", "Rate codes require the official money-and-banking lookup.", "Series coverage varies by bank and rate code."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Bank Negara Malaysia via data.gov.my
---

# data.gov.my Annual Interest Rates

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV
and Parquet downloads:

- `https://storage.data.gov.my/finsector/interest_rates_annual.csv`
- `https://storage.data.gov.my/finsector/interest_rates_annual.parquet`

## Status

**Status:** Current

**Freshness:** File last updated 2026-04-05; observations extend through 2025

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 31,371-byte file. It
contains 707 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers annual deposit, base, savings, and lending rates for
commercial and investment banks from 1980 through 2025.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Annual observation date in YYYY-MM-DD format. |
| `bank` | string | Commercial or investment bank category. |
| `rate` | string | Interest-rate series code. |
| `value` | number | Annual average interest rate in percent. |

## Known quirks

- Annual dates use 1 January.
- Values are annual averages and can retain many decimal places.
- The 18 rate codes require the official money-and-banking lookup.
- Not every bank/rate combination spans the entire date range.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/finsector/interest_rates_annual.csv" \
  -o /tmp/interest_rates_annual.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Bank Negara Malaysia via data.gov.my.

## Sample

- [samples/dgm_interest_rates_annual.csv](../samples/dgm_interest_rates_annual.csv)
- [samples/dgm_interest_rates_annual.json](../samples/dgm_interest_rates_annual.json)
