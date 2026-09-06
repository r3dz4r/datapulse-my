---
type: "Dataset"
title: "OpenDOSM Annual Fertility"
description: "DataPulse projection of OpenDOSM Annual Fertility from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/demography/fertility.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/demography/fertility.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_fertility.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Annual Fertility is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:edf56742fdbaccd38f206be51f83b8c2c23aeb20ebaa7b1bf07ec18fa9abef4c`
- `record_count`: `536`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_fertility.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
