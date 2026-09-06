---
type: "Dataset"
title: "Annual Nominal GDP by Income Component"
description: "DataPulse projection of Annual Nominal GDP by Income Component from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=gdp_annual_nominal_income"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=gdp_annual_nominal_income","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_gdp_annual_nominal_income.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 156
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Nominal GDP by Income Component is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:278cd6e5c8ef6cbed84321da88f79d9111690a9a87d92ee050d0100b3a51e1c9`
- `record_count`: `156`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_gdp_annual_nominal_income.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
