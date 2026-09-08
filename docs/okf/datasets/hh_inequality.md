---
type: "Dataset"
title: "Income Inequality"
description: "DataPulse projection of Income Inequality from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=hh_inequality"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=hh_inequality","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/hh_inequality.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2024-02-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Income Inequality is published by dosm and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `2`
- `first_row_hash`: `shape-v1:de54249e866f7cec4f4c3ae573d270842b965edacc9b0cde11f9c6bcf7914707`
- `record_count`: `21`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/hh_inequality.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
