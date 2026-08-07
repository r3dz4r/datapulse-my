---
dataset_id: exchangerates_daily_1200
last_checked: 2026-08-07T05:42:15Z
status: fresh
freshness_delta: 0 days
next_expected_update: 2026-08-03
record_count: ~7000
date_range: 1997-01-02 to 2026-07-31
schema_version: 1.0
schema_drift: none
known_quirks: ["four daily endpoints at fixed times (0900, 1130, 1200, 1700 MYT)", "returns full history back to 1997", "the 1200 noon middle rate is the most cited reference"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Bank Negara Malaysia via data.gov.my
---

# BNM Daily Exchange Rates (1200)

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200

## Last checked

2026-08-07 at 05:42:15 UTC.

## File size

The checked resource is 8,704,576 bytes.

## Coverage

The endpoint returns roughly 7,000 historical records, covering 1997-01-02
through 2026-07-31. Rates are BNM reference rates published in Kuala Lumpur.

## Schema

Each record contains `date` (`YYYY-MM-DD`), a consistently `middle`
`rate_type`, and 27 ISO currency fields:

`aed`, `aud`, `bnd`, `cad`, `chf`, `cny`, `egp`, `eur`, `gbp`, `hkd`, `idr`,
`inr`, `jpy`, `khr`, `krw`, `mmk`, `npr`, `nzd`, `php`, `pkr`, `sar`, `sgd`,
`thb`, `twd`, `usd`, `vnd`, and `xdr`.

The middle rate is the average of the buying and selling rates.

## Known quirks

- BNM publishes four daily endpoints at 0900, 1130, 1200, and 1700 MYT.
- The endpoint returns the full history rather than only the latest record.
- The noon rate is the most cited reference and is consistently a middle rate.

## Breaking changes

None observed.

## Sample

- [samples/exchangerates_daily_1200.json](samples/exchangerates_daily_1200.json)

## Reproducibility

```sh
curl "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_1200&limit=1"
```

## Licence

Licensed under the Open Government Licence (Malaysia).

Attribution: Bank Negara Malaysia via data.gov.my.
