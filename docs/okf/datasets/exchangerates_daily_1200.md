---
type: "Dataset"
title: "BNM Daily Exchange Rates (1200)"
description: "DataPulse projection of BNM Daily Exchange Rates (1200) from BNM."
resource: "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_1200"
tags: ["data.gov.my (BNM)","non-vertical","daily (weekdays, 1200 MYT)"]
sources:
  - {"id": "bnm","resource": "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_1200","title": "BNM"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-11-17T07:15:52Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Source: Bank Negara Malaysia"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/exchangerates_daily_1200.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-11-18T00:00:00Z"
datapulse:stale_after_basis: "weekday_cadence"
---

# Summary

BNM Daily Exchange Rates (1200) is published by BNM and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `29`
- `first_row_hash`: `shape-v1:13f660c4f6f9f45dcccbe6aaa992df67dd0e0a8fc7f8a58d9da9e9eeb5172e11`
- `record_count`: `18886`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/exchangerates_daily_1200.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
