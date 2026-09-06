---
type: "Dataset"
title: "Monthly Core Consumer Price Index"
description: "DataPulse projection of Monthly Core Consumer Price Index from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/cpi/cpi_2d_core.csv"
tags: ["OpenDOSM (also indexed by data.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/cpi/cpi_2d_core.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/cpi_core.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 1428
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Core Consumer Price Index is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:68091df250cbdea54c87dfcc916fa81fd0c2e05be4ad94a5c97c4a2d6ee698e7`
- `record_count`: `1442`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/cpi_core.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
