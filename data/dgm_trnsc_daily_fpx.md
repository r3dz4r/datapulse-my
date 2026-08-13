---
dataset_id: dgm_trnsc_daily_fpx
last_checked: 2026-08-12T16:16:35Z
last_checked: 2026-08-12T16:16:35Z
status: fresh
freshness_delta: 1 days
next_expected_update: daily
record_count: 7242
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This dataset is provided with the highest practical timeliness (updated by 2am daily for data up to the previous day) due to its high potential for use in nowcasting and forecasting models. However, there may occasional revisions to ensure eventual consistency with the monthly payment statistics published by the Central Bank of Malaysia (BNM). Furthermore, users should note that data for 2024-11-24 is missing at this time; this will be rectified by 1 March 2026."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Payments Network Malaysia and Bank Negara Malaysia via data.gov.my
---

# Daily FPX Transactions

## Status

**Status:** Fresh

**Freshness:** 1 days

HTTP 200

## Last checked

2026-08-12 at 16:16:35 UTC.

## File size

The checked resource is 605,558 bytes.

## Provenance

Payments Network Malaysia and Bank Negara Malaysia publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=trnsc_daily_fpx
- [Official catalogue metadata](https://data.gov.my/data-catalogue/trnsc_daily_fpx)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/trnsc_daily_fpx) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This dataset is provided with the highest practical timeliness (updated by 2am daily for data up to the previous day) due to its high potential for use in nowcasting and forecasting models. However, there may occasional revisions to ensure eventual consistency with the monthly payment statistics published by the Central Bank of Malaysia (BNM). Furthermore, users should note that data for 2024-11-24 is missing at this time; this will be rectified by 1 March 2026.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=trnsc_daily_fpx" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Payments Network Malaysia and Bank Negara Malaysia via data.gov.my.
