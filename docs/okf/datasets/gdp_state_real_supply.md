---
type: "Dataset"
title: "Annual Real GDP by State & Economic Sector"
description: "DataPulse projection of Annual Real GDP by State & Economic Sector from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=gdp_state_real_supply"
tags: ["data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=gdp_state_real_supply","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/gdp_state_real_supply.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Real GDP by State & Economic Sector is published by dosm and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:d406eed49ae2671e8dd9037749aec84b740cbd6cbf84af954f8d83eefa742b12`
- `record_count`: `2163`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/gdp_state_real_supply.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
