---
type: "Dataset"
title: "OpenDOSM Annual Population by State"
description: "DataPulse projection of OpenDOSM Annual Population by State from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/population/population_state.csv"
tags: ["OpenDOSM (storage.dosm.gov.my) (also indexed by data.gov.my)","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/population/population_state.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/population_state.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2027-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Annual Population by State is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:e3b9aec099d47a8667f28359f964d1004c32ea02265fa682871809714b322b6e`
- `record_count`: `270063`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/population_state.md). The probe is described by [the data_gov_my_storage_dosm_gov_my attested computation](/computations/data-gov-my-storage-dosm-gov-my.md).
