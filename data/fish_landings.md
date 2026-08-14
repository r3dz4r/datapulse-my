---
dataset_id: dgm_fish_landings
last_checked: 2026-08-14T04:59:27Z
status: stale
freshness_delta: 987 days
next_expected_update: overdue
record_count: 1368
date_range: 2018-01-01 to 2023-12-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use the first day of the month.", "All-coast and Malaysia aggregate rows coexist with detailed rows and must not be summed together.", "Values are metric tonnes landed by registered establishments, not fish caught or personal-consumption fishing.", "Johor appears in both east- and west-coast data; national totals may differ slightly because of rounding."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Department of Fisheries Malaysia via data.gov.my
---

# data.gov.my Monthly Landings of Marine Fish by State

## Status

**Status:** Stale

**Freshness:** 987 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 42,011 bytes.

## Provenance

Department of Fisheries Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/agriculture/fish_landings.csv`
- `https://storage.data.gov.my/agriculture/fish_landings.parquet`

Catalogue description: [Monthly landings of marine fish by state and coast from 2018 to 2023.](https://data.gov.my/data-catalogue/fish_landings).

## Coverage

The dataset covers Malaysia (national, coast, and 14 state-level areas) from 2018-01-01 through 2023-12-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | The date in YYYY-MM-DD format, with DD set to 01 as the data is at monthly frequency |
| `coast` | string | The coast where the fish was landed; either all coasts ('all'), the east coast of Peninsular Malaysia ('east'), west coast of Peninsular Malaysia ('west') or Borneo ('borneo') |
| `state` | string | The state where the fish was landed; one of 14 states (excludiing W.P. Kuala Lumpur and W.P. Putrajaya, which do not have coastlines) or Malaysia (included for ease of analysis). It should be noted that Johor is a part of both the east and west coast data. |
| `landings` | integer | The total landings of marine fish in metric tonnes |

## Known quirks

- Monthly dates use the first day of the month.
- All-coast and Malaysia aggregate rows coexist with detailed rows and must not be summed together.
- Values are metric tonnes landed by registered establishments, not fish caught or personal-consumption fishing.
- Johor appears in both east- and west-coast data; national totals may differ slightly because of rounding.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/agriculture/fish_landings.csv" \
  -o /tmp/fish_landings.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Department of Fisheries Malaysia via data.gov.my.

## Sample

- [samples/dgm_fish_landings.csv](../samples/dgm_fish_landings.csv)
- [samples/dgm_fish_landings.json](../samples/dgm_fish_landings.json)
