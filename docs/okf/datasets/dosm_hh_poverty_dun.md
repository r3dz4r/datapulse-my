---
type: "Dataset"
title: "Poverty by DUN"
description: "DataPulse projection of Poverty by DUN from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=hh_poverty_dun"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=hh_poverty_dun","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_hh_poverty_dun.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 1800
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Poverty by DUN is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:ffaf8213e8a52ac26c908b0441ddb1655c8b9f4d53fe89e7180b2987d6b43de0`
- `record_count`: `1800`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_hh_poverty_dun.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
