---
type: "Dataset"
title: "Industrial Production Index (IPI)"
description: "DataPulse projection of Industrial Production Index (IPI) from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=ipi"
tags: ["DOSM via data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=ipi","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dosm_ipi.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 395
stale_after: "2026-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Industrial Production Index (IPI) is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:f8b631dd4f333f8e4391ddc7f10c3dc54c8d980bf1f1f8d861285a8eb9190fbf`
- `record_count`: `401`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_ipi.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
