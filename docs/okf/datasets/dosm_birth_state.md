---
type: "Dataset"
title: "OpenDOSM Annual Births by State"
description: "DataPulse projection of OpenDOSM Annual Births by State from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/demography/birth_state.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/demography/birth_state.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-10-05T06:46:30Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Data source: Department of Statistics Malaysia"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_birth_state.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Annual Births by State is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:a0c0ddff0ee40313695d28e1f2b6a1f259b38017e8702e7aadb27e73b215a917`
- `record_count`: `390`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_birth_state.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
