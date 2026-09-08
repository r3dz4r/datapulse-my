---
type: "Dataset"
title: "TFR and ASFR by State"
description: "DataPulse projection of TFR and ASFR by State from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=fertility_state"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=fertility_state","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_fertility_state.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 3000
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

TFR and ASFR by State is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:38d62b310b86ea1e7d21ff207bc0313709b0e977f7176b2c0e2d4693501dccf6`
- `record_count`: `3000`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_fertility_state.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
