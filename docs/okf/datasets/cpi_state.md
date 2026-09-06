---
type: "Dataset"
title: "Monthly CPI by State & Division (2-digit)"
description: "DataPulse projection of Monthly CPI by State & Division (2-digit) from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=cpi_state"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=cpi_state","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/cpi_state.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly CPI by State & Division (2-digit) is published by dosm and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:7619f609b3a28fc838a97c8976f2ddd3d72929453fb9e8ea638d9220af23038a`
- `record_count`: `44576`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/cpi_state.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
