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
  - {"by": "process:datapulse-health-timer","at": "2026-10-28T15:21:35Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Source: Bank Negara Malaysia"
datapulse:real_status: "degraded"
datapulse:health_report: "/data/exchangerates_daily_1700.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-10-29T00:00:00Z"
datapulse:stale_after_basis: "weekday_cadence"
---

# Summary

BNM Daily Exchange Rates (1700) is published by BNM and tracked by DataPulse. The latest published probe classifies it as `degraded`.

# Schema

- `column_count`: `29`
- `first_row_hash`: `shape-v1:1b34f4b6bfaa6901be7287270e714581aaa96e853ab5dcc8853b7f12fb86b144`
- `record_count`: `17316`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/exchangerates_daily_1700.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
