---
type: "Dataset"
title: "Monthly Trade by SITC Section (1 digit)"
description: "DataPulse projection of Monthly Trade by SITC Section (1 digit) from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=trade_sitc_1d"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=trade_sitc_1d","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/trade_sitc_1d.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Trade by SITC Section (1 digit) is published by dosm and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:4784fb356b6f8a6ce523fe1094f5bc80e450f033bcb3034bd97e46f8548b0700`
- `record_count`: `3509`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/trade_sitc_1d.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
