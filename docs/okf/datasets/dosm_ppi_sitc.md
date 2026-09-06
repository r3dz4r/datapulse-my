---
type: "Dataset"
title: "Monthly PPI by SITC Section (1 digit)"
description: "DataPulse projection of Monthly PPI by SITC Section (1 digit) from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=ppi_sitc"
tags: ["DOSM via data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=ppi_sitc","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_ppi_sitc.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 5229
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly PPI by SITC Section (1 digit) is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:e476b1d321707a7b169fd5682e26192e8f00feb55957593b6c97508e9b464cc7`
- `record_count`: `5256`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_ppi_sitc.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
