---
type: "Dataset"
title: "Monthly Industrial Production Index by Item"
description: "DataPulse projection of Monthly Industrial Production Index by Item from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/ipi/ipi_5d.csv"
tags: ["OpenDOSM (also indexed by data.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/ipi/ipi_5d.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via OpenDOSM"
datapulse:real_status: "stale"
datapulse:health_report: "/data/ipi_5d.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 52536
stale_after: "2026-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Industrial Production Index by Item is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:0074028a5cff458f1be94b1d3850d38887e7b12851a144d9d447534f174d56b1`
- `record_count`: `52932`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/ipi_5d.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
