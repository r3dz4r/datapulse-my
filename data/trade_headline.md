---
dataset_id: trade_headline
last_checked: 2026-08-10T00:26:32Z
status: stale
freshness_delta: 131 days
next_expected_update: overdue
record_count: 743
date_range: 2000-01-01 to 2026-04-01
schema_version: 1.0
schema_drift: none
known_quirks: ["monthly dates use the first day of the month", "series mixes absolute values with growth rates", "some component fields are blank in early observations"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Monthly Trade Headline

## Status

**Status:** Stale

**Freshness:** 131 days

HTTP 200

## Last checked

2026-08-10 at 00:26:32 UTC.

## File size

The checked resource is 56,287 bytes.

## Provenance

DOSM publishes this national dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/trade/trade_headline.csv`
- `https://storage.dosm.gov.my/trade/trade_headline.parquet`

## Coverage

The dataset contains national monthly Malaysian merchandise-trade headlines
from January 2000 through April 2026. It has no subnational geographic field.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | `abs`, `growth_yoy`, or `growth_mom`. |
| `date` | date | Month start date in `YYYY-MM-DD` format. |
| `exports` | number | Total exports. |
| `exports_domestic` | number | Domestic exports; blank in some early rows. |
| `re_exports` | number | Re-exports; blank in some early rows. |
| `imports` | number | Total imports. |
| `imports_retained` | number | Retained imports; blank in some early rows. |
| `total` | number | Total trade. |
| `balance` | number | Trade balance. |

## Known quirks

- Monthly dates use the first day of each month.
- Absolute amounts and percentage growth rates share the measure columns.
- `exports_domestic`, `re_exports`, and `imports_retained` each have 96 blank
  values in early observations.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/trade/trade_headline.csv" \
  -o /tmp/trade_headline.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_trade_headline.csv](../samples/dosm_trade_headline.csv)
- [samples/dosm_trade_headline.json](../samples/dosm_trade_headline.json)
