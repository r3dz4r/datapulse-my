---
type: "Dataset"
title: "Monthly Unemployment by Duration"
description: "DataPulse projection of Monthly Unemployment by Duration from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=lfs_month_duration"
tags: ["DOSM via data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=lfs_month_duration","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dosm_lfs_month_duration.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 125
stale_after: "2026-06-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Unemployment by Duration is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `8`
- `first_row_hash`: `shape-v1:d4504e16e296abc3158971ed2fed1337e7658c06248b69fb3daa3387b36c3446`
- `record_count`: `125`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_lfs_month_duration.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
