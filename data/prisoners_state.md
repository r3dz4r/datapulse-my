---
dataset_id: dgm_prisoners_state
last_checked: 2026-08-14T04:59:27Z
status: stale
freshness_delta: 1686 days
next_expected_update: overdue
record_count: 234
date_range: 2017-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January, while counts are snapshots at 31 December.", "Both-sex rows coexist with female and male rows and must not be summed together.", "Counts combine convicted and remand prisoners and should not be interpreted as crime or recidivism measures."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Malaysian Prison Department via data.gov.my
---

# data.gov.my Prisoners by State and Sex

## Status

**Status:** Stale

**Freshness:** 1686 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 7,097 bytes.

## Provenance

Malaysian Prison Department publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/publicsafety/prisoners_state.csv`
- `https://storage.data.gov.my/publicsafety/prisoners_state.parquet`

Catalogue description: [Number of prisoners in Malaysia by state and sex from 2017 to 2022.](https://data.gov.my/data-catalogue/prisoners_state).

## Coverage

The dataset covers Malaysia (national and 12 reported state-level areas) from 2017-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | The date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at annual frequency |
| `state` | string | One of 16 states |
| `sex` | string | Either both sexes ('both'), male ('male') or female ('female') |
| `prisoners` | integer | The number of prisoners as of 31st December in the given year |

## Known quirks

- Annual dates use 1 January, while counts are snapshots at 31 December.
- Both-sex rows coexist with female and male rows and must not be summed together.
- Counts combine convicted and remand prisoners and should not be interpreted as crime or recidivism measures.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/publicsafety/prisoners_state.csv" \
  -o /tmp/prisoners_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Malaysian Prison Department via data.gov.my.

## Sample

- [samples/dgm_prisoners_state.csv](../samples/dgm_prisoners_state.csv)
- [samples/dgm_prisoners_state.json](../samples/dgm_prisoners_state.json)
