---
dataset_id: exchangerates_daily_1130
last_checked: 2026-08-10T00:45:12Z
status: aging
freshness_delta: 3 days
next_expected_update: 2026-08-03
record_count: 11388
date_range: 1997-01-02 to 2026-07-31
schema_version: 1.0
schema_drift: none
known_quirks: ["four daily endpoints at fixed times (0900, 1130, 1200, 1700 MYT)", "returns full history back to 1997", "historically has fewer currency columns (mostly buying rate)", "rate_type varies (buying/selling/middle)"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Bank Negara Malaysia via data.gov.my
---

# BNM Daily Exchange Rates (1130)

## Status

**Status:** Aging

**Freshness:** 3 days

HTTP 200

## Last checked

2026-08-10 at 00:45:12 UTC.

## File size

The checked resource is 1,712,483 bytes.

## Coverage

The endpoint returns roughly 7,000 historical records, covering 1997-01-02
through 2026-07-31. Rates are BNM reference rates published in Kuala Lumpur.

## Schema

Each record contains `date`, `rate_type`, and a subset of currencies (mostly
buying rate). Historical records commonly expose `aud`, `cad`, `eur`, `gbp`,
`jpy`, `sgd`, and `usd`; consumers must tolerate missing or null currencies.

## Known quirks

- BNM publishes four daily endpoints at 0900, 1130, 1200, and 1700 MYT.
- The endpoint returns the full history rather than only the latest record.
- The 1130 history has fewer currency columns and is mostly buying-rate data.
- `rate_type` can vary. A bank sells foreign currency at the buying rate, buys
  it at the selling rate, and the middle rate is their average.

## Breaking changes

None observed.

## Sample

- [samples/exchangerates_daily_1130.json](samples/exchangerates_daily_1130.json)

## Reproducibility

```sh
curl "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_1130&limit=1"
```

## Licence

Licensed under the Open Government Licence (Malaysia).

Attribution: Bank Negara Malaysia via data.gov.my.
