---
type: "Dataset"
title: "Monthly PPI by Stage of Processing"
description: "DataPulse projection of Monthly PPI by Stage of Processing from dosm."
resource: "https://storage.dosm.gov.my/ppi/ppi_sop.csv"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/ppi/ppi_sop.csv","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-16T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/ppi_sop.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
---

# Summary

Monthly PPI by Stage of Processing is published by dosm and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:d88d93218e8de7b706f577d75267bf547bb695b265fe4e33b5e8bb33d8838ca6`
- `record_count`: `12221`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/ppi_sop.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
