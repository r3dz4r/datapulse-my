---
dataset_id: dosm_crime_district
last_checked: 2026-08-09T08:37:11Z
status: stale
freshness_delta: 1316 days
next_expected_update: overdue
record_count: 19152
date_range: 2016-01-01 to 2023-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["annual observations use January 1 as the date", "includes Malaysia aggregate rows", "no Labuan state rows", "upstream API not refreshed since 2024-10-16; DOSM publishes newer crime data via portal releases (latest: Crime Statistics, Malaysia, 2025 on 16 Oct 2025) but not to this open-data dataset"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM, data from PDRM
---

# OpenDOSM Crime by District and Type (Annual)

## Status

**Status:** Stale

**Freshness:** 1316 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 1,038,732 bytes.

## Provenance

PDRM's data-terbuka page links to an archive.data.gov.my dataset page that is
no longer reachable. The authoritative live source for the same PDRM data is
the OpenDOSM catalogue entry published by DOSM:
`https://open.dosm.gov.my/data-catalogue/crime_district`.

This report therefore treats OpenDOSM—not the dead PDRM-linked archive—as the
source endpoint. DOSM publishes the files at:

- `https://storage.data.gov.my/publicsafety/crime_district.csv`
- `https://storage.data.gov.my/publicsafety/crime_district.parquet`

The underlying crime data is sourced from PDRM and republished by DOSM.

## Coverage

The dataset spans eight annual dates from 2016-01-01 through 2023-01-01. It
contains 15 state labels, including W.P. Kuala Lumpur and Malaysia aggregate
rows, but no Labuan rows. The 19,152 records cover two categories (`assault`
and `property`) and 13 type values:

- `all`
- `break_in`
- `causing_injury`
- `murder`
- `rape`
- `robbery_gang_armed`
- `robbery_gang_unarmed`
- `robbery_solo_armed`
- `robbery_solo_unarmed`
- `theft_other`
- `theft_vehicle_lorry`
- `theft_vehicle_motorcar`
- `theft_vehicle_motorcycle`

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | State or Malaysia aggregate label. |
| `district` | string | Police district or aggregate district label. |
| `category` | string | Broad crime category: `assault` or `property`. |
| `type` | string | Aggregate or specific crime type. |
| `date` | date | Annual observation date in `YYYY-MM-DD` format. |
| `crimes` | integer | Recorded number of crimes. |

## Known quirks

- Annual observations use January 1 to represent each reporting year.
- Aggregate rows coexist with district-level and specific-type rows.
- The state coverage includes W.P. Kuala Lumpur and Malaysia totals but not
  Labuan.
- **Upstream staleness:** the open-data endpoint has not been refreshed since
  2024-10-16 — the latest year in the data is 2023. DOSM publishes newer crime
  statistics via its portal releases (latest: *Crime Statistics, Malaysia,
  2025*, released 16 Oct 2025, covering 2024) but has **not** mirrored them to
  this open-data dataset. Data consumers should treat 2024+ figures as
  available only from DOSM's portal PDFs, not from this API.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/publicsafety/crime_district.csv" \
  -o /tmp/crime.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence. This differs
from the Open Government Licence used by the other DataPulse MY entries.

Attribution: DOSM via OpenDOSM, data from PDRM.

## Sample

- [samples/dosm_crime_district.csv](../samples/dosm_crime_district.csv)
- [samples/dosm_crime_district.json](../samples/dosm_crime_district.json)
