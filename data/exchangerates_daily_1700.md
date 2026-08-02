---
dataset_id: exchangerates_daily_1700
last_checked: 2026-07-31T08:00:00Z
status: healthy
freshness_delta: 0 days
next_expected_update: 2026-08-03
record_count: ~7000
date_range: 1997-01-02 to 2026-07-31
schema_version: 1.0
schema_drift: none
known_quirks: ["four daily endpoints at fixed times (0900, 1130, 1200, 1700 MYT)", "returns full history back to 1997", "captures end-of-day rates", "rate_type varies (buying/selling/middle)"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Bank Negara Malaysia via data.gov.my
---

# BNM Daily Exchange Rates (1700)

## Status

**Status:** Healthy  
**Freshness:** 0 days  
**Refresh frequency:** Daily on weekdays at 1700 MYT

The API is reachable and the latest observed record is dated 2026-07-31. This
endpoint captures BNM's end-of-day exchange rates.

## Last checked

2026-07-31 at 08:00:00 UTC.

## Coverage

The endpoint returns roughly 7,000 historical records, covering 1997-01-02
through 2026-07-31. Rates are BNM reference rates published in Kuala Lumpur.

## Schema

Each record contains `date` (`YYYY-MM-DD`), `rate_type` (`buying`, `middle`, or
`selling`), and 27 ISO currency fields:

`aed`, `aud`, `bnd`, `cad`, `chf`, `cny`, `egp`, `eur`, `gbp`, `hkd`, `idr`,
`inr`, `jpy`, `khr`, `krw`, `mmk`, `npr`, `nzd`, `php`, `pkr`, `sar`, `sgd`,
`thb`, `twd`, `usd`, `vnd`, and `xdr`.

## Known quirks

- BNM publishes four daily endpoints at 0900, 1130, 1200, and 1700 MYT.
- The endpoint returns the full history rather than only the latest record.
- The 1700 publication captures end-of-day rates.
- `rate_type` varies by row. A bank sells foreign currency at the buying rate,
  buys it at the selling rate, and the middle rate is their average.

## Breaking changes

None observed.

## Sample

- [samples/exchangerates_daily_1700.json](samples/exchangerates_daily_1700.json)

## Reproducibility

```sh
curl "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_1700&limit=1"
```

## Licence

Licensed under the Open Government Licence (Malaysia).

Attribution: Bank Negara Malaysia via data.gov.my.
