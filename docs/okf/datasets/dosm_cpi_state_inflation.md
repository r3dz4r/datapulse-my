---
type: "Dataset"
title: "OpenDOSM Monthly CPI Inflation by State and Division"
description: "DataPulse projection of OpenDOSM Monthly CPI Inflation by State and Division from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/cpi/cpi_2d_state_inflation.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/cpi/cpi_2d_state_inflation.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-26T02:49:53Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/dosm_cpi_state_inflation.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-09-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Monthly CPI Inflation by State and Division is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:19c921f8f3ab60390e0b796f6bbaeb69397d72aac73828246f8076cf41ebb09a`
- `record_count`: `44576`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_cpi_state_inflation.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
