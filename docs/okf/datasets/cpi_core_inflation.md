---
type: "Dataset"
title: "Monthly Core CPI Inflation"
description: "DataPulse projection of Monthly Core CPI Inflation from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv"
tags: ["OpenDOSM (also indexed by data.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/cpi_core_inflation.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 1414
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Core CPI Inflation is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:4df27604fe443770c1c21819b12eb2363292aef62e8d746c030c6b3e53790154`
- `record_count`: `1428`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/cpi_core_inflation.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
