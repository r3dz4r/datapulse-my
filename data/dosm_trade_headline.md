---
dataset_id: dosm_trade_headline
last_checked: 2026-08-02T16:01:47Z
status: stale
freshness_delta: 74 days since file update
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

## Provenance

DOSM publishes this national dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/trade/trade_headline.csv`
- `https://storage.dosm.gov.my/trade/trade_headline.parquet`

## Status

**Status:** Stale

**Freshness:** File last updated 2026-05-20; observations end in April 2026

**Refresh frequency:** Monthly

The CSV endpoint returned HTTP 200 and its expected 56,287-byte file. It
contains 743 data rows, but the latest observation is more than one monthly
cycle behind the check date.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

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
