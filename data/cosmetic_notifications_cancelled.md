---
id: "cosmetic_notifications_cancelled"
title: "Cancelled Cosmetic Product Notifications"
source_url: "https://storage.data.gov.my/healthcare/cosmetic_notifications_cancelled.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-16T02:09:20Z
last_observed: null
last_modified: 2026-08-15T23:51:05Z
record_count: 124
column_count: 5
status: fresh
notes: "Tier-1 wave E newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: cosmetic_notifications_cancelled
freshness_delta: 0 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "National Pharmaceutical Regulatory Agency via data.gov.my"
---

# Cancelled Cosmetic Product Notifications

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 14,131 bytes.

## Provenance

National Pharmaceutical Regulatory Agency publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/healthcare/cosmetic_notifications_cancelled.csv`

## Coverage

Malaysia. Latest source observation: not encoded in a date field.

## Schema

The verified CSV contains 5 columns: `notif_no`, `product`, `holder`, `manufacturer`, `substance_detected`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/cosmetic_notifications_cancelled.csv"
curl -sS "https://storage.data.gov.my/healthcare/cosmetic_notifications_cancelled.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: National Pharmaceutical Regulatory Agency via data.gov.my.
