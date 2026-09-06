---
type: "Dataset"
title: "Household Income by State & Percentile"
description: "DataPulse projection of Household Income by State & Percentile from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=hies_state_percentile"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=hies_state_percentile","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_hies_state_percentile.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 10000
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Household Income by State & Percentile is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:e4d4dc03380e4d9c17db97ce6f8b0f42609475e1bc43980c0dfca32c2374df18`
- `record_count`: `19200`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_hies_state_percentile.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
