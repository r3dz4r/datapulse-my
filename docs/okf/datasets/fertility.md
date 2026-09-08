---
type: "Dataset"
title: "TFR and ASFR"
description: "DataPulse projection of TFR and ASFR from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=fertility"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=fertility","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/fertility.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2024-02-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

TFR and ASFR is published by dosm and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:ccfaf36d478d9f2777591b5af60a011d188606624cfa2747d7e7b83c3b7012f0`
- `record_count`: `536`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/fertility.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
