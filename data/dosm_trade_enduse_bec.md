---
dataset_id: dosm_trade_enduse_bec
last_checked: 2026-08-05T14:31:11Z
status: aging
freshness_delta: 77 days
next_expected_update: overdue
record_count: 14332
date_range: 2010-01-01 to 2026-04-01
schema_version: 1.0
schema_drift: none
known_quirks: ["monthly dates use the first day of the month", "BEC codes must remain strings", "000 is an aggregate code", "series mixes absolute values with growth rates"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Monthly Trade by End Use (BEC)

## Status

**Status:** Aging

**Freshness:** 77 days

HTTP 200

## Last checked

2026-08-05 at 14:31:11 UTC.

## File size

The checked resource is 611,406 bytes.

## Provenance

DOSM publishes this national dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/trade/trade_enduse_bec.csv`
- `https://storage.dosm.gov.my/trade/trade_enduse_bec.parquet`

## Coverage

The dataset contains national monthly Malaysian retained-import observations
from January 2010 through April 2026. It has no subnational geographic field.
Rows cover seven end-use groups and 19 BEC codes.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | `abs`, `growth_yoy`, or `growth_mom`. |
| `end_use` | string | Retained-import aggregate or one of six end-use groups. |
| `bec` | string | Three-digit Broad Economic Category code. |
| `date` | date | Month start date in `YYYY-MM-DD` format. |
| `imports` | number | Import value in the unit defined by `series`. |

## Known quirks

- Monthly dates use the first day of each month.
- BEC codes must remain strings so leading zeroes are preserved.
- BEC `000` is an aggregate and coexists with detailed codes.
- Absolute import values and percentage growth rates share `imports`.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/trade/trade_enduse_bec.csv" \
  -o /tmp/trade_enduse_bec.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_trade_enduse_bec.csv](../samples/dosm_trade_enduse_bec.csv)
- [samples/dosm_trade_enduse_bec.json](../samples/dosm_trade_enduse_bec.json)
