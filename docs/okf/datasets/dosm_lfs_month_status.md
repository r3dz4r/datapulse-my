---
type: "Dataset"
title: "Monthly Employment by Status in Employment"
description: "DataPulse projection of Monthly Employment by Status in Employment from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=lfs_month_status"
tags: ["DOSM via data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=lfs_month_status","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dosm_lfs_month_status.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 250
stale_after: "2026-06-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Employment by Status in Employment is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `7`
- `first_row_hash`: `shape-v1:6fe1380fcb9066837b87a802ec7dbc58c01a1b2ff1b0dc15138ebe52b531b617`
- `record_count`: `250`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_lfs_month_status.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
