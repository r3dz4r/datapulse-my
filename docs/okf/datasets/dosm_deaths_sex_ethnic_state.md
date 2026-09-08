---
type: "Dataset"
title: "Annual Deaths by State, Sex, & Ethnicity"
description: "DataPulse projection of Annual Deaths by State, Sex, & Ethnicity from National Registration Department and Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=deaths_sex_ethnic_state"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "jpn","resource": "https://api.data.gov.my/data-catalogue?id=deaths_sex_ethnic_state","title": "National Registration Department and Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "National Registration Department and Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_deaths_sex_ethnic_state.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 8190
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Deaths by State, Sex, & Ethnicity is published by National Registration Department and Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:4d4a5f6c103953f8f8bec541907a92d6a5031aea7a16a38ba900de4610549ee4`
- `record_count`: `8190`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_deaths_sex_ethnic_state.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
