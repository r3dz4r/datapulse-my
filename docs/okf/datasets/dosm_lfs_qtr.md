---
type: "Dataset"
title: "OpenDOSM Quarterly Labour Force Statistics"
description: "DataPulse projection of OpenDOSM Quarterly Labour Force Statistics from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/labour/lfs_qtr.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","quarterly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/labour/lfs_qtr.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-10-10T11:37:57Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Data source: Department of Statistics Malaysia"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_lfs_qtr.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-08-17T00:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Quarterly Labour Force Statistics is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `8`
- `first_row_hash`: `shape-v1:af7d2905be69979a98e3e54a08a9c1f0e899c3d0c6e9eef396fe5a2b06fb36d2`
- `record_count`: `66`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_lfs_qtr.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
