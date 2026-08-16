---
dataset_id: dgm_drug_addicts_age
last_checked: 2026-08-16T02:09:20Z
status: fresh
freshness_delta: 212 days
next_expected_update: annual
record_count: 783
date_range: 2015-01-01 to 2023-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Total-age rows coexist with detailed age groups and must not be summed together.", "Counts may exclude unreported cases."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: National Anti-Drugs Agency and Ministry of Home Affairs via data.gov.my
---

# data.gov.my Drug Addicts by State & Age Group

## Status

**Status:** Fresh

**Freshness:** 212 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 24,028 bytes.

## Provenance

National Anti-Drugs Agency publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/publicsafety/drug_addicts_age.csv`
- `https://storage.data.gov.my/publicsafety/drug_addicts_age.parquet`

Catalogue description: [This dataset provides yearly statistics on the number of drug addicts in Malaysia, broken down by state and age group. It offers insights into the demographic distribution of drug addiction across different regions and age categories in the country.](https://data.gov.my/data-catalogue/drug_addicts_age).

## Coverage

The dataset covers Malaysia (national and 16 state-level areas) from 2015-01-01 through 2023-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | The date on which the data was recorded, in YYYY-MM-DD format. |
| `state` | string | The state in Malaysia where the data on drug addiction was recorded. Includes all states and federal territories. |
| `age_group` | string | The age group of the drug addicts, categorized into specific ranges such as 16-19, 20-24, etc. |
| `addicts` | integer | The number of drug addicts recorded for the specified state and age group. |

## Known quirks

- Annual dates use 1 January.
- Total-age rows coexist with detailed age groups and must not be summed together.
- Counts may exclude unreported cases.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/publicsafety/drug_addicts_age.csv" \
  -o /tmp/drug_addicts_age.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: National Anti-Drugs Agency and Ministry of Home Affairs via data.gov.my.

## Sample

- [samples/dgm_drug_addicts_age.csv](../samples/dgm_drug_addicts_age.csv)
- [samples/dgm_drug_addicts_age.json](../samples/dgm_drug_addicts_age.json)
