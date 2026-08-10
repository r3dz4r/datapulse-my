---
dataset_id: dosm_marriages_state
last_checked: 2026-08-10T10:07:26Z
status: stale
freshness_delta: 1682 days
next_expected_update: overdue
record_count: 192
date_range: 2017-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "The file has no Malaysia aggregate.", "Each state-year has separate female and male rows.", "Counts and marriage rates use different units."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Marriages by State and Sex

## Status

**Status:** Stale

**Freshness:** 1682 days

HTTP 200

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The checked resource is 7,202 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM
as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/demography/marriages_state.csv`
- `https://storage.dosm.gov.my/demography/marriages_state.parquet`

## Coverage

The dataset covers annual marriages for female and male populations across 16
Malaysian state-level areas from 2017 through 2022.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `date` | date | Annual observation date in YYYY-MM-DD format. |
| `sex` | string | Female or male population series. |
| `abs` | integer | Source-reported absolute number of marriages. |
| `rate` | number | Source-reported marriage rate. |

## Known quirks

- Annual dates use 1 January.
- There is no Malaysia aggregate row.
- Every state-year has separate female and male rows; filtering by sex is
  required before aggregating people counts.
- `abs` is a count while `rate` is not additive.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/demography/marriages_state.csv" \
  -o /tmp/marriages_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_marriages_state.csv](../samples/dosm_marriages_state.csv)
- [samples/dosm_marriages_state.json](../samples/dosm_marriages_state.json)
