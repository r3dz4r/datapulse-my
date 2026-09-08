---
type: "Dataset"
title: "OpenDOSM Crime by District & Type (Annual)"
description: "DataPulse projection of OpenDOSM Crime by District & Type (Annual) from DOSM Malaysia (data sourced from PDRM)."
resource: "https://storage.data.gov.my/publicsafety/crime_district.csv"
tags: ["OpenDOSM (data.gov.my storage)","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.data.gov.my/publicsafety/crime_district.csv","title": "DOSM Malaysia (data sourced from PDRM)"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM, data from PDRM"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dosm_crime_district.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2024-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Crime by District & Type (Annual) is published by DOSM Malaysia (data sourced from PDRM) and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:032baf8bffd204931df94783b66e8ed1267528cba937012831209c53a163a704`
- `record_count`: `19152`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_crime_district.md). The probe is described by [the opendosm_data_gov_my_storage attested computation](/computations/opendosm-data-gov-my-storage.md).
