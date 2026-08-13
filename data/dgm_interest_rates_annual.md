---
dataset_id: dgm_interest_rates_annual
last_checked: 2026-08-11T14:21:08Z
status: fresh
freshness_delta: 127 days
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

## Status

**Status:** Fresh

**Freshness:** 127 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 31,371 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV
and Parquet downloads:

- `https://storage.data.gov.my/finsector/interest_rates_annual.csv`
- `https://storage.data.gov.my/finsector/interest_rates_annual.parquet`

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
