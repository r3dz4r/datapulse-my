---
type: "Dataset"
title: "Headline Services Producer Price Index (SPPI)"
description: "DataPulse projection of Headline Services Producer Price Index (SPPI) from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=sppi"
tags: ["DOSM via data.gov.my","non-vertical","quarterly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=sppi","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_sppi.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 130
stale_after: "2026-05-19T00:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Headline Services Producer Price Index (SPPI) is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:3c1ed6c7efccd8b70e949f8db9193094c7f65527f6f9ab63cf3ed660b16cba2c`
- `record_count`: `130`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_sppi.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
