---
dataset_id: dosm_birth_state
last_checked: 2026-08-02T17:18:27Z
status: current
freshness_delta: 26 days since file update
next_expected_update: annual
record_count: 390
date_range: 2000-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "The file has no Malaysia aggregate.", "W.P. Putrajaya observations begin in 2010.", "Absolute counts and crude birth rates use different units."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Births by State

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM
as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/demography/birth_state.csv`
- `https://storage.dosm.gov.my/demography/birth_state.parquet`

## Status

**Status:** Current

**Freshness:** File last updated 2026-07-07; observations extend through 2024

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 12,308-byte file. It
contains 390 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers annual live births for 16 Malaysian state-level areas from
2000 through 2024; W.P. Putrajaya begins in 2010.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `date` | date | Annual observation date in YYYY-MM-DD format. |
| `abs` | integer | Registered live births. |
| `rate` | number | Source-reported crude birth rate. |

## Known quirks

- Annual dates use 1 January.
- There is no Malaysia aggregate row.
- W.P. Putrajaya has 15 observations beginning in 2010; the other areas have
  25 observations beginning in 2000.
- `abs` is a count while `rate` is a crude birth rate and cannot be summed.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/demography/birth_state.csv" \
  -o /tmp/birth_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_birth_state.csv](../samples/dosm_birth_state.csv)
- [samples/dosm_birth_state.json](../samples/dosm_birth_state.json)
