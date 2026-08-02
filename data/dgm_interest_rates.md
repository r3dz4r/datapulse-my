---
dataset_id: dgm_interest_rates
last_checked: 2026-08-02T16:47:48Z
status: stale
freshness_delta: 118 days since file update
next_expected_update: overdue
record_count: 5712
date_range: 1997-01-01 to 2026-02-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use the first day of the month.", "Rate codes require the official money-and-banking lookup table.", "Fixed-deposit series methodology changes in August 2000.", "The Standardised Base Rate replaced the Base Rate for new retail floating-rate loans in August 2022."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Bank Negara Malaysia via data.gov.my
---

# data.gov.my Monthly Interest Rates

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/finsector/interest_rates.csv`
- `https://storage.data.gov.my/finsector/interest_rates.parquet`

Catalogue description: [monthly deposit, base, and lending rates monitored by Bank Negara Malaysia](https://data.gov.my/data-catalogue/interestrates).

## Status

**Status:** Stale

**Freshness:** File last updated 2026-04-05; observations end on 2026-02-01

**Refresh frequency:** Monthly

The CSV endpoint returned HTTP 200 and its expected 228,401-byte file. It
contains 5,712 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national banking system) from 1997-01-01 through 2026-02-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `bank` | string | Banking institution type. |
| `rate` | string | Interest-rate series code. |
| `value` | number | Observed value; units depend on the dataset and series. |

## Known quirks

- Monthly dates use the first day of the month.
- Rate codes require the official money-and-banking lookup table.
- Fixed-deposit series methodology changes in August 2000.
- The Standardised Base Rate replaced the Base Rate for new retail floating-rate loans in August 2022.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/finsector/interest_rates.csv" \
  -o /tmp/interest_rates.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Bank Negara Malaysia via data.gov.my.

## Sample

- [samples/dgm_interest_rates.csv](../samples/dgm_interest_rates.csv)
- [samples/dgm_interest_rates.json](../samples/dgm_interest_rates.json)
