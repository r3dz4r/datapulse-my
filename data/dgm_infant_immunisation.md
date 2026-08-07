---
dataset_id: dgm_infant_immunisation
last_checked: 2026-08-07T07:25:52Z
status: stale
freshness_delta: 1314 days
next_expected_update: overdue
record_count: 120
date_range: 2000-01-01 to 2023-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Coverage rates can exceed 100% because aggregate immunisation counts use official population estimates as the denominator.", "Measles data ends after the transition to MMR, and eight rate values are blank."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Ministry of Health Malaysia via data.gov.my
---

# data.gov.my Infant Immunisation Coverage

## Status

**Status:** Stale

**Freshness:** 1314 days

HTTP 200

## Last checked

2026-08-07 at 07:25:52 UTC.

## File size

The checked resource is 2,683 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/healthcare/infant_immunisation.csv`
- `https://storage.data.gov.my/healthcare/infant_immunisation.parquet`

Catalogue description: [Annual infant immunisation coverage rates at national level.](https://data.gov.my/data-catalogue/infant_immunisation).

## Coverage

The dataset covers Malaysia (national) from 2000-01-01 through 2023-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | The year of the immunisation data in YYYY-MM-DD format, with MM-DD set to 01-01 because the data is annual. |
| `disease` | string | The disease for which immunisation coverage is reported, such as measles, MMR, DPT, Hepatitis B, or polio. |
| `rate` | number | The immunisation coverage rate as a percentage. |

## Known quirks

- Annual dates use 1 January.
- Coverage rates can exceed 100% because aggregate immunisation counts use official population estimates as the denominator.
- Measles data ends after the transition to MMR, and eight rate values are blank.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/healthcare/infant_immunisation.csv" \
  -o /tmp/infant_immunisation.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Ministry of Health Malaysia via data.gov.my.

## Sample

- [samples/dgm_infant_immunisation.csv](../samples/dgm_infant_immunisation.csv)
- [samples/dgm_infant_immunisation.json](../samples/dgm_infant_immunisation.json)
