---
dataset_id: dgm_local_authority_sex
last_checked: 2026-08-11T14:21:08Z
status: stale
freshness_delta: 1683 days
next_expected_update: overdue
record_count: 322
date_range: 2019-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January and represent composition at the start of the year.", "State-level `All` rows coexist with local-authority rows and must not be averaged together.", "Percentages use filled positions as the denominator and exclude vacancies."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Ministry of Housing and Local Government via data.gov.my
---

# data.gov.my Female Representation in Local Authorities

## Status

**Status:** Stale

**Freshness:** 1683 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 17,005 bytes.

## Provenance

Ministry of Housing and Local Government publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/publicadmin/local_authority_sex.csv`
- `https://storage.data.gov.my/publicadmin/local_authority_sex.parquet`

Catalogue description: [Proportion of women and men in Malaysian local authorities.](https://data.gov.my/data-catalogue/local_authority_sex).

## Coverage

The dataset covers Malaysia (state and local-authority level) from 2019-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or national aggregate. |
| `local_authority` | string | Nama pihak berkuasa tempatan |
| `date` | date | The date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at annual frequency. |
| `female` | number | Women as a percentage of total filled positions |
| `male` | number | Men as a percentage of total filled positions |

## Known quirks

- Annual dates use 1 January and represent composition at the start of the year.
- State-level `All` rows coexist with local-authority rows and must not be averaged together.
- Percentages use filled positions as the denominator and exclude vacancies.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/publicadmin/local_authority_sex.csv" \
  -o /tmp/local_authority_sex.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Ministry of Housing and Local Government via data.gov.my.

## Sample

- [samples/dgm_local_authority_sex.csv](../samples/dgm_local_authority_sex.csv)
- [samples/dgm_local_authority_sex.json](../samples/dgm_local_authority_sex.json)
