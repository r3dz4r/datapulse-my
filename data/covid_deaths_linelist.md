---
id: "covid_deaths_linelist"
title: "COVID-19 Deaths Line List"
source_url: "https://storage.data.gov.my/healthcare/covid_deaths_linelist.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "annual"
last_checked: 2026-08-10T10:07:26Z
last_observed: 2024-05-18
last_modified: 2025-06-04T03:46:32Z
record_count: 37351
column_count: 15
status: aging
notes: "Tier-1 wave G newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: covid_deaths_linelist
freshness_delta: 814 days
next_expected_update: "annual"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Ministry of Health Malaysia via data.gov.my"
---

# COVID-19 Deaths Line List

## Status

**Status:** Aging

**Freshness:** 814 days

HTTP 200

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The checked resource is 2,638,461 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/healthcare/covid_deaths_linelist.csv`

## Coverage

Malaysia. Latest source observation: 2024-05-18.

## Schema

The verified CSV contains 15 columns: `date`, `date_announced`, `date_positive`, `date_dose1`, `date_dose2`, `date_dose3`, `brand1`, `brand2`, `brand3`, `state`, `age`, `male`, `bid`, `malaysian`, `comorb`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/covid_deaths_linelist.csv"
curl -sS "https://storage.data.gov.my/healthcare/covid_deaths_linelist.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Ministry of Health Malaysia via data.gov.my.
