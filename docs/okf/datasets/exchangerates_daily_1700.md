---
type: "Dataset"
title: "BNM Daily Exchange Rates (1700)"
description: "DataPulse projection of BNM Daily Exchange Rates (1700) from BNM."
resource: "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_1700"
tags: ["data.gov.my (BNM)","non-vertical","daily (weekdays, 1700 MYT)"]
sources:
  - {"id": "bnm","resource": "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_1700","title": "BNM"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-08T03:01:24Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/exchangerates_daily_1700.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-09-07T00:00:00Z"
datapulse:stale_after_basis: "weekday_cadence"
---

# Summary

BNM Daily Exchange Rates (1700) is published by BNM and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `29`
- `first_row_hash`: `shape-v1:f55dd70c5f7e6baf0e5c309f7a1d3748189b8bede932a71850330a6d42c2ddc8`
- `record_count`: `17205`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/exchangerates_daily_1700.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
