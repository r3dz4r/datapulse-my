---
type: "Dataset"
title: "Households with Access to Electricity"
description: "DataPulse projection of Households with Access to Electricity from Energy Commission and Malaysian electricity utilities."
resource: "https://api.data.gov.my/data-catalogue?id=electricity_access"
tags: ["data.gov.my (OpenAPI)","non-vertical","annual"]
sources:
  - {"id": "energy_commission","resource": "https://api.data.gov.my/data-catalogue?id=electricity_access","title": "Energy Commission and Malaysian electricity utilities"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Energy Commission and Malaysian electricity utilities via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/electricity_access.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 44
stale_after: "2022-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Households with Access to Electricity is published by Energy Commission and Malaysian electricity utilities and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:c18c37a4ed55b4964d4f71ef8287343c03cff2bc3bf69cd92714dc9584a4151b`
- `record_count`: `44`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/electricity_access.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
