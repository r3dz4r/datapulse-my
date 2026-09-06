---
type: "Dataset"
title: "Annual Nominal GDP by Expenditure Type"
description: "DataPulse projection of Annual Nominal GDP by Expenditure Type from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=gdp_annual_nominal_demand"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=gdp_annual_nominal_demand","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_gdp_annual_nominal_demand.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 137
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Nominal GDP by Expenditure Type is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:5ad28b6a5daf4f5cdb0d8b44b502c6ea2d841a71fbbb499234bc388a46a80b97`
- `record_count`: `137`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_gdp_annual_nominal_demand.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
