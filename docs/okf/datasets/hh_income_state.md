---
type: "Dataset"
title: "Household Income by State"
description: "DataPulse projection of Household Income by State from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=hh_income_state"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=hh_income_state","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/hh_income_state.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2024-02-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Household Income by State is published by dosm and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:5543f1c876ae803a63694ccc3b3997904b4025dca74a59e6e7ce666df1965d7f`
- `record_count`: `319`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/hh_income_state.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
