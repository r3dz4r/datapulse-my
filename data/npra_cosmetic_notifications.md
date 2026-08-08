---
id: "npra_cosmetic_notifications"
title: "NPRA Notified Cosmetic Products"
source_url: "https://storage.data.gov.my/healthcare/cosmetic_notifications.csv"
source_name: "NPRA via data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "weekly"
last_checked: 2026-08-08T06:00:59Z
last_observed: null
last_modified: 2026-08-06T22:31:24Z
record_count: 241538
column_count: 4
status: fresh
notes: "Agent-ready mirror of cosmetic products notified with NPRA. Probe weekly and use the existing freshness taxonomy; do not interpret notification as product approval."
dataset_id: npra_cosmetic_notifications
freshness_delta: 1 days
next_expected_update: "weekly"
schema_version: 1.0
schema_drift: none
known_quirks:
  - "NPRA describes cosmetics as notified, not registered or approved"
  - "date_notif may contain future administrative dates and is not a reliable publication-freshness signal"
breaking_changes: []
attribution: "National Pharmaceutical Regulatory Agency, Ministry of Health Malaysia via data.gov.my"
---

# NPRA Notified Cosmetic Products

## Status

**Status:** Fresh

**Freshness:** 1 days

HTTP 200

## Provenance

NPRA's consumer material and product-search service distinguish cosmetic
products notified with NPRA from registered pharmaceutical products:

- `https://www.npra.gov.my/index.php/en/consumers.html`
- `https://www.npra.gov.my/index.php/my/consumers-2/maklumat/carian-produk-berdaftar-bernotifikasi.html`

The agent-ready full notification payload is the official data.gov.my mirror:

- `https://storage.data.gov.my/healthcare/cosmetic_notifications.csv`

## Schema

The verified CSV contains four columns: `notif_no`, `product`, `company`, and
`date_notif`.

## Freshness semantics

The weekly check uses the source `Last-Modified` header. Future administrative
values in `date_notif` are rejected as freshness evidence. Records older than
the configured cadence move through the existing `aging` and `stale` statuses.

Notification is a regulatory status and must not be presented as NPRA approval
of a cosmetic product.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/cosmetic_notifications.csv"
curl -sS "https://storage.data.gov.my/healthcare/cosmetic_notifications.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: National
Pharmaceutical Regulatory Agency, Ministry of Health Malaysia via data.gov.my.
