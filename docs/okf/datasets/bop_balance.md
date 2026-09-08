---
type: "Dataset"
title: "Balance of Payments by Account"
description: "DataPulse projection of Balance of Payments by Account from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/bop/bop_balance.csv"
tags: ["OpenDOSM (also indexed by data.gov.my)","non-vertical","quarterly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/bop/bop_balance.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/bop_balance.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 325
stale_after: "2026-08-17T00:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Balance of Payments by Account is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:d88c73cfbd47c106e0abd5f4f49f5fc036b84cd89e409777347e2ad234bbccfd`
- `record_count`: `330`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bop_balance.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
