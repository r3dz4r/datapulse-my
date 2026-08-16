---
dataset_id: dgm_interestrates_annual
last_checked: 2026-08-16T02:09:20Z
last_checked: 2026-08-16T02:09:20Z
status: aging
freshness_delta: 592 days
next_expected_update: annual
record_count: 707
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: There are several nuances to bear in mind when using this data: 1. From August 2000 onwards, the Fixed Deposit Rate series for Commercial Banks and Investment Banks have been revised. Data for x-month fixed deposit rate refers to the quoted rate for that particular maturity alone. (Data prior to this date continue to reflect the average maturity). 2. Effective 1 August 2022, the Standardised Base Rate replaced the Base Rate (BR) as the reference rate for new retail floating-rate loans. Existing BR- and BLR-based loans applied before the effective date will continue to be referenced against the BR and BLR respectively. However, after the effective date, the BR and BLR will move exactly in tandem with the Standardised Base Rate as any adjustments to the Standardised Base Rate will simultaneously be reflected in the corresponding adjustments to the BR and BLR. 3. Since March 2012, the following banks were included in the computation of the average lending rate: Industrial and Commercial Bank of China from November 2010 onwards; Sumitomo Mitsui Banking Corporation from May 2011 onwards; Mizuho Corporation Bank (M) Berhad and BNP Paribas Malaysia Berhad from December 2011 onwards."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Bank Negara Malaysia via data.gov.my
---

# Annual Interest Rates

## Status

**Status:** Aging

**Freshness:** 592 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 63,197 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=interestrates_annual
- [Official catalogue metadata](https://data.gov.my/data-catalogue/interestrates_annual)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/interestrates_annual) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: There are several nuances to bear in mind when using this data: 1. From August 2000 onwards, the Fixed Deposit Rate series for Commercial Banks and Investment Banks have been revised. Data for x-month fixed deposit rate refers to the quoted rate for that particular maturity alone. (Data prior to this date continue to reflect the average maturity). 2. Effective 1 August 2022, the Standardised Base Rate replaced the Base Rate (BR) as the reference rate for new retail floating-rate loans. Existing BR- and BLR-based loans applied before the effective date will continue to be referenced against the BR and BLR respectively. However, after the effective date, the BR and BLR will move exactly in tandem with the Standardised Base Rate as any adjustments to the Standardised Base Rate will simultaneously be reflected in the corresponding adjustments to the BR and BLR. 3. Since March 2012, the following banks were included in the computation of the average lending rate: Industrial and Commercial Bank of China from November 2010 onwards; Sumitomo Mitsui Banking Corporation from May 2011 onwards; Mizuho Corporation Bank (M) Berhad and BNP Paribas Malaysia Berhad from December 2011 onwards.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=interestrates_annual" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Bank Negara Malaysia via data.gov.my.
