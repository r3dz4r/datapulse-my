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
  - {"by": "process:datapulse-health-timer","at": "2026-11-01T01:57:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Source: Bank Negara Malaysia"
datapulse:real_status: "aging"
datapulse:health_report: "/data/exchangerates_daily_0900.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-11-02T00:00:00Z"
datapulse:stale_after_basis: "weekday_cadence"
---

# Summary

BNM Daily Exchange Rates (0900) is published by BNM and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `29`
- `first_row_hash`: `shape-v1:98b1e238c94bb046b617feb3a930f72b315e2735f2bf91da1e747b3cdb93a7bc`
- `record_count`: `17288`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/exchangerates_daily_0900.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
