---
type: "Dataset"
title: "OpenDOSM Household Expenditure by DUN"
description: "DataPulse projection of OpenDOSM Household Expenditure by DUN from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/hies/hh_expenditure_dun.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","biennial to triennial (survey years)"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/hies/hh_expenditure_dun.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/dosm_hh_expenditure_dun.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2028-06-30T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Household Expenditure by DUN is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:a32cd98e330b2cd9c37823395c0ef3dca5c03aba25536ef61f3b637f7144730d`
- `record_count`: `1800`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_hh_expenditure_dun.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
