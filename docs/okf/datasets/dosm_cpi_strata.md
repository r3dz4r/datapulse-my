---
type: "Dataset"
title: "Monthly CPI by Strata & Division (2-digit)"
description: "DataPulse projection of Monthly CPI by Strata & Division (2-digit) from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=cpi_strata"
tags: ["DOSM via data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=cpi_strata","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_cpi_strata.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 5544
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly CPI by Strata & Division (2-digit) is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:0d3e24c567f718ed2bf08b33e942de4fd6d5d6a4acbbb3a1a59d8c44a10aaf9d`
- `record_count`: `5572`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_cpi_strata.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
