---
type: "Dataset"
title: "Income Inequality by State"
description: "DataPulse projection of Income Inequality by State from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=hh_inequality_state"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=hh_inequality_state","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/hh_inequality_state.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2024-02-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Income Inequality by State is published by dosm and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:9ea7579f997ac963d053b9b887e860b5bdf6dce8ee80955489d9a87733578811`
- `record_count`: `289`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/hh_inequality_state.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
