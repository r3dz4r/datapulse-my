---
type: "Dataset"
title: "Annual Marriages"
description: "DataPulse projection of Annual Marriages from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=marriages"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=marriages","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dosm_marriages.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 12
stale_after: "2023-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Marriages is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:08e2d14d4c8fe3553b4281f9eb57c2d4794a100f52ed2d6ba3e8a7e7c2adb752`
- `record_count`: `12`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_marriages.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
