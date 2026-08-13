---
dataset_id: dosm_trade_sitc_1d
last_checked: 2026-08-13T02:46:04Z
status: aging
freshness_delta: 73 days
next_expected_update: monthly
record_count: 3498
date_range: 2000-01-01 to 2026-06-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use the first day of the month.", "SITC section codes must remain strings.", "The overall aggregate coexists with sections 0 through 9.", "The latest two months are provisional."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Monthly Trade by SITC Section

## Status

**Status:** Aging

**Freshness:** 73 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 138,635 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/trade/trade_sitc_1d.csv`
- `https://storage.dosm.gov.my/trade/trade_sitc_1d.parquet`

Catalogue description: [monthly exports and imports by one-digit SITC commodity section](https://open.dosm.gov.my/data-catalogue/trade_sitc_1d).

## Coverage

The dataset covers Malaysia (national) from 2000-01-01 through 2026-06-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `section` | string | One-digit SITC section code or overall aggregate. |
| `exports` | number | Export value in ringgit. |
| `imports` | number | Import value in ringgit. |

## Known quirks

- Monthly dates use the first day of the month.
- SITC section codes must remain strings.
- The overall aggregate coexists with sections 0 through 9.
- The latest two months are provisional.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/trade/trade_sitc_1d.csv" \
  -o /tmp/trade_sitc_1d.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_trade_sitc_1d.csv](../samples/dosm_trade_sitc_1d.csv)
- [samples/dosm_trade_sitc_1d.json](../samples/dosm_trade_sitc_1d.json)
