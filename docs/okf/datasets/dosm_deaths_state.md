---
type: "Dataset"
title: "Annual Deaths by State"
description: "DataPulse projection of Annual Deaths by State from National Registration Department and Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=deaths_state"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "jpn","resource": "https://api.data.gov.my/data-catalogue?id=deaths_state","title": "National Registration Department and Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "National Registration Department and Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_deaths_state.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 390
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Deaths by State is published by National Registration Department and Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:ef6e67f0491b060948c4f7b0cdfdb8c1c1a18a34f7dd367fede98550f3d9788c`
- `record_count`: `390`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_deaths_state.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
