---
dataset_id: dosm_hh_inequality_district
last_checked: 2026-08-02T19:11:50Z
status: current
freshness_delta: 27 days since file update
next_expected_update: biennial to triennial (survey years)
record_count: 480
date_range: 2019-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Only the 2019, 2022, and 2024 survey years are present.", "District coverage varies across survey years, so the 172 labels do not form a complete panel.", "Gini values are coefficients on a zero-to-one scale."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Income Inequality by District

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_inequality_district.csv`
- `https://storage.dosm.gov.my/hies/hh_inequality_district.parquet`

## Status

**Status:** Current

**Freshness:** File last updated 2026-07-06; observations extend through 2024-01-01

**Refresh frequency:** Biennial to triennial (survey years)

The CSV endpoint returned HTTP 200 and its expected 16,296-byte file. It contains 480 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers 16 state-level areas and 172 district labels across the available survey years from 2019-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `district` | string | Administrative district. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `gini` | number | Gini coefficient reported by the source. |

## Known quirks

- Only the 2019, 2022, and 2024 survey years are present.
- District coverage varies across survey years, so the 172 labels do not form a complete panel.
- Gini values are coefficients on a zero-to-one scale.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_inequality_district.csv" \
  -o /tmp/hh_inequality_district.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_inequality_district.csv](../samples/dosm_hh_inequality_district.csv)
- [samples/dosm_hh_inequality_district.json](../samples/dosm_hh_inequality_district.json)
