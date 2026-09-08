---
type: "Dataset"
title: "Monthly Producer Price Index by Group"
description: "DataPulse projection of Monthly Producer Price Index by Group from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/ppi/ppi_3d.csv"
tags: ["OpenDOSM (also indexed by data.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/ppi/ppi_3d.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/ppi_3d.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 37044
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Producer Price Index by Group is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:50ad1e0211236c0fb918e765d517e5d43b8d77a7f4eda489150be9d716b93eef`
- `record_count`: `37260`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/ppi_3d.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
