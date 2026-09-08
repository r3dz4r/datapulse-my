---
type: "Dataset"
title: "Annual Nominal GDP by Economic Sector"
description: "DataPulse projection of Annual Nominal GDP by Economic Sector from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=gdp_annual_nominal_supply"
tags: ["data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=gdp_annual_nominal_supply","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/gdp_annual_nominal_supply.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Nominal GDP by Economic Sector is published by dosm and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:5d3b5f8234257d523201c7197fdb4d1f4abba562f39b22e37b834779401642be`
- `record_count`: `147`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/gdp_annual_nominal_supply.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
