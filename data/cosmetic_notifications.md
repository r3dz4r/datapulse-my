---
id: "cosmetic_notifications"
title: "Cosmetic Product Notifications"
source_url: "https://storage.data.gov.my/healthcare/cosmetic_notifications.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-10T04:08:14Z
last_observed: null
last_modified: 2026-08-08T09:56:14Z
record_count: 241749
column_count: 4
status: fresh
notes: "Tier-1 wave E newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: cosmetic_notifications
freshness_delta: 1 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "National Pharmaceutical Regulatory Agency via data.gov.my"
---

# Cosmetic Product Notifications

## Status

**Status:** Fresh

**Freshness:** 1 days

HTTP 200

## Last checked

2026-08-10 at 04:08:14 UTC.

## File size

The checked resource is 23,631,729 bytes.

## Provenance

National Pharmaceutical Regulatory Agency publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/healthcare/cosmetic_notifications.csv`

## Coverage

Malaysia. Latest source observation: 2036-10-07.

## Schema

The verified CSV contains 4 columns: `notif_no`, `product`, `company`, `date_notif`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/cosmetic_notifications.csv"
curl -sS "https://storage.data.gov.my/healthcare/cosmetic_notifications.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: National Pharmaceutical Regulatory Agency via data.gov.my.
