---
id: "vaxreg_covid_demog"
title: "COVID-19 Vaccination Registrations by Demographic Group"
source_url: "https://storage.data.gov.my/healthcare/vaxreg_covid_demog.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "annual"
last_checked: 2026-08-10T10:07:26Z
last_observed: 2022-02-22
last_modified: 2024-01-02T01:00:56Z
record_count: 198560
column_count: 5
status: stale
notes: "Tier-1 wave G newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: vaxreg_covid_demog
freshness_delta: 1630 days
next_expected_update: "annual"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Ministry of Health Malaysia via data.gov.my"
---

# COVID-19 Vaccination Registrations by Demographic Group

## Status

**Status:** Stale

**Freshness:** 1630 days

HTTP 200

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The checked resource is 7,063,745 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/healthcare/vaxreg_covid_demog.csv`

## Coverage

Malaysia. Latest source observation: 2022-02-22.

## Schema

The verified CSV contains 5 columns: `date`, `state`, `sex`, `age`, `registrations`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/vaxreg_covid_demog.csv"
curl -sS "https://storage.data.gov.my/healthcare/vaxreg_covid_demog.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Ministry of Health Malaysia via data.gov.my.
