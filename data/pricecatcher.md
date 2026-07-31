---
dataset_id: pricecatcher
last_checked: 2026-07-31T08:00:00Z
status: healthy
freshness_delta: 0 days
next_expected_update: 2026-08-31
file_size_bytes: 2286215
file_count: 3 (main + 2 lookups)
schema_version: 1.0
schema_drift: none
known_quirks: ["not available via OpenAPI - bulk download only", "premise_code and item_code are integer foreign keys requiring lookup tables", "filename pattern is pricecatcher_YYYY-MM.parquet", "monthly release cadence"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: KPDN Malaysia via data.gov.my
---

# PriceCatcher (Daily Grocery Prices)

## Status

**Status:** Healthy  
**Freshness:** 0 days  
**Refresh frequency:** Monthly

The July 2026 main file and both lookup tables are reachable. No schema drift
or breaking changes were observed.

## Last checked

2026-07-31 at 08:00:00 UTC.

## File size

The main `pricecatcher_2026-07.parquet` file is 2,286,215 bytes. The dataset
also depends on two lookup files: `lookup_item.parquet` (16,398 bytes) and
`lookup_premise.parquet` (140,582 bytes).

## Schema

The main file contains four fields:

- `date` — date in `YYYY-MM-DD` format
- `premise_code` — integer foreign key into `lookup_premise.parquet`
- `item_code` — integer foreign key into `lookup_item.parquet`
- `price` — float price in Malaysian ringgit (RM)

The item lookup maps `item_code` to item name, unit, and category. The premise
lookup maps `premise_code` to premise name, address, district, and state.

## Known quirks

- PriceCatcher is not available through the data.gov.my OpenAPI. Consumers
  must download the bulk Parquet or CSV files.
- The main file stores `premise_code` and `item_code` as integer foreign keys.
  Join both lookup tables before presenting or analysing the records.
- Monthly Parquet files follow the `pricecatcher_YYYY-MM.parquet` filename
  pattern.
- Releases are monthly, and the filename suffix represents the publish month.

## Breaking changes

None observed.

## Reproducibility

Check reachability and reported file sizes with:

```sh
curl -I https://storage.data.gov.my/pricecatcher/pricecatcher_2026-07.parquet
curl -I https://storage.data.gov.my/pricecatcher/lookup_item.parquet
curl -I https://storage.data.gov.my/pricecatcher/lookup_premise.parquet
```

## Licence

Licensed under the Open Government Licence (Malaysia).

Attribution: KPDN Malaysia via data.gov.my.
