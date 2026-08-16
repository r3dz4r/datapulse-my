---
dataset_id: fuelprice
last_checked: 2026-08-16T02:09:20Z
status: fresh
freshness_delta: 3 days
next_expected_update: 2026-08-06
record_count: 947
date_range: 2017-03-30 to 2026-07-30
schema_version: 1.1
schema_drift: none
known_quirks:
  - offset parameter silently ignored
  - date filter silently ignored
  - default sort ascending
  - client-side dedup by date required
  - subsidy fields (ron95_skps, diesel_budi, diesel_skds, ron95_budi95) nullable for older dates
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Ministry of Finance Malaysia via data.gov.my
---

# fuelprice — Weekly Fuel Price

## Status

**Status:** Fresh

**Freshness:** 3 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 205,248 bytes.

## Known quirks

1. **offset parameter silently ignored.** The API does not paginate. The client must use `limit=500` with default ascending sort to capture all rows, then deduplicate client-side by `date`.
2. **date filter silently ignored.** Passing `date=YYYY-MM-DD` returns the full history regardless. Filtering must be done client-side.
3. **Subsidy fields nullable on older dates.** The 4 subsidy variants (ron95_skps, diesel_budi, diesel_skds, ron95_budi95) are not populated before subsidy programs started; missing values are valid, not corruption.

## Schema (14 fields)

| Field | Type | Nullable | Definition |
| --- | --- | --- | --- |
| `date` | string | no | YYYY-MM-DD, the price effective date (every Thursday since 2017-03-30) |
| `ron95` | float | no | RON 95 retail price, RM/litre |
| `ron97` | float | no | RON 97 retail price, RM/litre |
| `diesel` | float | no | Diesel retail price, RM/litre |
| `diesel_eastmsia` | float | no | Diesel retail price in East Malaysia, RM/litre |
| `ron95_skps` | float? | yes | RON 95 subsidy (Sabah/Sarawak), RM/litre. Absent before subsidy started. |
| `diesel_budi` | float? | yes | Diesel Budi (subsidised), RM/litre. Absent before program started. |
| `diesel_skds` | float? | yes | Diesel subsidy (Sabah/Sarawak), RM/litre. Absent before program started. |
| `ron95_budi95` | float? | yes | RON 95 Budi95 (subsidised), RM/litre. Absent before program started. |
| `series_type` | string | no | Always "level" (point-in-time price, not flow) |
| `title` | string | no | Always "fuelprice YYYY-MM-DD" |
| `agency` | string | no | Always "MOF" (Ministry of Finance) |
| `dataset_id` | string | no | Always "fuelprice" |
| `url` | string | no | Source URL: https://data.gov.my/data-catalogue/fuelprice |

## Breaking changes

None since initial scrape (2026-07-30).

## Sample

- [samples/fuelprice.csv](samples/fuelprice.csv)
- [samples/fuelprice.json](samples/fuelprice.json)

## Reproducibility

Anyone with `curl` and `jq` can verify:

```bash
curl "https://api.data.gov.my/data-catalogue?id=fuelprice&limit=500" | jq '. | length'
# Expected: ~500 raw rows, 472 unique after deduplication by date

curl "https://api.data.gov.my/data-catalogue?id=fuelprice&limit=1" | jq '.[0]'
# Inspect a single row's structure
```

## Licence

[Open Government Licence (Malaysia)](https://www.data.gov.my/pages/terms-of-use)
Attribution: Ministry of Finance Malaysia via data.gov.my
