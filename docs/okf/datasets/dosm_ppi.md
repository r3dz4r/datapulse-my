---
type: "Dataset"
title: "OpenDOSM Monthly Producer Price Index"
description: "DataPulse projection of OpenDOSM Monthly Producer Price Index from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/ppi/ppi.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/ppi/ppi.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_ppi.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Monthly Producer Price Index is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:a9098ba0ebd97899eb8c3bd2f9039b778a81b7190f578e49dee50b50eb4598dc`
- `record_count`: `584`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_ppi.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
