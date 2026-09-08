---
type: "Dataset"
title: "Poverty"
description: "DataPulse projection of Poverty from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=hh_poverty"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=hh_poverty","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/hh_poverty.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2024-02-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Poverty is published by dosm and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:afea8e6c0b68c26fa6809e4af97f7aa853c1694192f1746ec133a6f99fc37010`
- `record_count`: `21`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/hh_poverty.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
