---
id: "st_max_demand_mw"
title: "Maximum Demand (MW) — Malaysia"
source_url: "https://meih.st.gov.my/statistics?_Eng_Statistic_WAR_STOASPublicPortlet__eventId=ViewStatistic&categoryId=10&flowId=39"
source_name: "meih.st.gov.my (ST)"
licence: "Open Government Licence (Malaysia)"
refresh_frequency: "monthly"
last_checked: 2026-09-06T11:34:39Z
last_observed: 2021-01-01
last_modified: null
record_count: 33
column_count: 5
status: stale
notes: "Unprobed Suruhanjaya Tenaga MyEnergyStats HTML dashboard; health remains unknown until the first DataPulse probe."
dataset_id: st_max_demand_mw
freshness_delta: 2074 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Suruhanjaya Tenaga (ST) via meih.st.gov.my"
---

# Maximum Demand (MW) — Malaysia

## Status

**Status:** Stale

**Freshness:** 2074 days

ST report table returned a valid year

## Last checked

2026-09-06 at 11:34:39 UTC.

## File size

The checked resource is 61,288 bytes.

## Provenance

Suruhanjaya Tenaga (ST) publishes this dataset through meih.st.gov.my:

- `https://meih.st.gov.my/statistics?_Eng_Statistic_WAR_STOASPublicPortlet__eventId=ViewStatistic&categoryId=10&flowId=39`

## Coverage

Malaysia. Latest source observation is not available until the first probe.

## Schema

The HTML dashboard content shape will be recorded by the first DataPulse content-shape probe.

## Known quirks

- The dashboard's freshness signal is the latest year-month detected in server-rendered text.

## Reproducibility

```sh
curl -sS -I "https://meih.st.gov.my/statistics?_Eng_Statistic_WAR_STOASPublicPortlet__eventId=ViewStatistic&categoryId=10&flowId=39"
```

## Licence

Licensed under Open Government Licence (Malaysia). Attribution: Suruhanjaya Tenaga (ST) via meih.st.gov.my.
