---
type: "Dataset"
title: "Malaysian Economic Indicators"
description: "DataPulse projection of Malaysian Economic Indicators from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=economic_indicators"
tags: ["DOSM via data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=economic_indicators","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/economic_indicators.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 425
stale_after: "2026-06-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Malaysian Economic Indicators is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:cb85d62578dd73deb55541be1aadc915114fd639ac3e6291176c7bda9136dce8`
- `record_count`: `425`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/economic_indicators.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
