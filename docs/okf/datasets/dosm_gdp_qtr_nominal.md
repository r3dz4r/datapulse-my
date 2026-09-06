---
type: "Dataset"
title: "OpenDOSM Quarterly Nominal GDP"
description: "DataPulse projection of OpenDOSM Quarterly Nominal GDP from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/gdp/gdp_qtr_nominal.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","quarterly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/gdp/gdp_qtr_nominal.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_gdp_qtr_nominal.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-08-17T00:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Quarterly Nominal GDP is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:fa4bd649f882bee506a7b2fb668dde7ba2a99adfc510149c8657f7e898bea002`
- `record_count`: `133`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_gdp_qtr_nominal.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
