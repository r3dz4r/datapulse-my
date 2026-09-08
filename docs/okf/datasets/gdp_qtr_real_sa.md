---
type: "Dataset"
title: "Quarterly Real GDP (Seasonally Adjusted)"
description: "DataPulse projection of Quarterly Real GDP (Seasonally Adjusted) from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=gdp_qtr_real_sa"
tags: ["data.gov.my","non-vertical","quarterly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=gdp_qtr_real_sa","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/gdp_qtr_real_sa.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-08-17T00:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Quarterly Real GDP (Seasonally Adjusted) is published by dosm and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:a13feafee352d107c56b1bc44c4deddca24ea8e9d8c7e144e7125323aed55606`
- `record_count`: `46`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/gdp_qtr_real_sa.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
