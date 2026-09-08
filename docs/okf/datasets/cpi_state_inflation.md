---
type: "Dataset"
title: "Monthly CPI Inflation by State & Division (2-digit)"
description: "DataPulse projection of Monthly CPI Inflation by State & Division (2-digit) from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=cpi_state_inflation"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=cpi_state_inflation","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/cpi_state_inflation.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly CPI Inflation by State & Division (2-digit) is published by dosm and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:97d01a3b8ddf8fa498f52e6f75aad3a773661d06fcb4b1c39eeffe2a6fa0c9dc`
- `record_count`: `44352`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/cpi_state_inflation.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
