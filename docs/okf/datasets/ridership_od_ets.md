---
type: "Dataset"
title: "KTMB ETS Origin-Destination Ridership"
description: "DataPulse projection of KTMB ETS Origin-Destination Ridership from Keretapi Tanah Melayu Berhad."
resource: "https://storage.data.gov.my/transportation/ktmb/ets_2026.csv"
tags: ["data.gov.my","non-vertical","daily"]
sources:
  - {"id": "ktmb","resource": "https://storage.data.gov.my/transportation/ktmb/ets_2026.csv","title": "Keretapi Tanah Melayu Berhad"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Keretapi Tanah Melayu Berhad via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/ridership_od_ets.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 507504
stale_after: "2026-09-06T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

KTMB ETS Origin-Destination Ridership is published by Keretapi Tanah Melayu Berhad and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:e31e5a55152ec3f528cedc488ce3207a71b3c095f1f64668ec6ecf7565f604b8`
- `record_count`: `574127`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/ridership_od_ets.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
