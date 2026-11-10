---
type: "Dataset"
title: "BNM Daily Exchange Rates (0900)"
description: "DataPulse projection of BNM Daily Exchange Rates (0900) from BNM."
resource: "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_0900"
tags: ["data.gov.my (BNM)","non-vertical","daily (weekdays, 0900 MYT)"]
sources:
  - {"id": "bnm","resource": "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_0900","title": "BNM"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-11-10T02:17:44Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Source: Bank Negara Malaysia"
datapulse:real_status: "degraded"
datapulse:health_report: "/data/exchangerates_daily_0900.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-11-11T00:00:00Z"
datapulse:stale_after_basis: "weekday_cadence"
---

# Summary

BNM Daily Exchange Rates (0900) is published by BNM and tracked by DataPulse. The latest published probe classifies it as `degraded`.

# Schema

- `column_count`: `29`
- `first_row_hash`: `shape-v1:cbbf1065608777a25c02fc2d59877213a4dca345927525e9ffffc9de7195a145`
- `record_count`: `17306`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/exchangerates_daily_0900.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
