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
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T16:20:14Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/exchangerates_daily_0900.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-09-07T00:00:00Z"
datapulse:stale_after_basis: "weekday_cadence"
---

# Summary

BNM Daily Exchange Rates (0900) is published by BNM and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `29`
- `first_row_hash`: `shape-v1:63b2273b90c7472f9b72d1f65bd27e35b3f45563f8205f2fa03df2ab601f75f7`
- `record_count`: `17171`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/exchangerates_daily_0900.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
