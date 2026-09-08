---
type: "Dataset"
title: "Annual CPI by Division (2-digit)"
description: "DataPulse projection of Annual CPI by Division (2-digit) from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=cpi_annual"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=cpi_annual","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_cpi_annual.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 559
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual CPI by Division (2-digit) is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:a8537ad92b7a2cebc1eb6986d90512023847f85c60286ae639790c750fba513d`
- `record_count`: `559`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_cpi_annual.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
