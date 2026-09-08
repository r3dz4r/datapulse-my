---
type: "Dataset"
title: "OpenDOSM Income Inequality by State"
description: "DataPulse projection of OpenDOSM Income Inequality by State from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/hies/hh_inequality_state.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","biennial to triennial (survey years)"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/hies/hh_inequality_state.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/dosm_hh_inequality_state.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2028-06-30T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Income Inequality by State is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:82a328f026dc42d4f9d7bca36371b130c1cf0710a75e97dc0f3802af23a0bc67`
- `record_count`: `289`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_hh_inequality_state.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
