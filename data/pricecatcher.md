---
dataset_id: pricecatcher
last_checked: 2026-08-07T07:25:52Z
status: fresh
freshness_delta: 0 days
next_expected_update: 2026-08-31
file_size_bytes: 618056
file_count: 3 (main + 2 lookups)
schema_version: 1.0
schema_drift: none
known_quirks: ["not available via OpenAPI - bulk download only", "premise_code and item_code are integer foreign keys requiring lookup tables", "filename pattern is pricecatcher_YYYY-MM.parquet", "monthly release cadence"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: KPDN Malaysia via data.gov.my
---

# PriceCatcher (Grocery Prices)

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200

## Last checked

2026-08-07 at 07:25:52 UTC.

## File size

The checked resource is 618,056 bytes.

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

## Sample

- [samples/pricecatcher.csv](samples/pricecatcher.csv)
- [samples/pricecatcher_lookup_item.csv](samples/pricecatcher_lookup_item.csv)
- [samples/pricecatcher_lookup_premise.csv](samples/pricecatcher_lookup_premise.csv)

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
