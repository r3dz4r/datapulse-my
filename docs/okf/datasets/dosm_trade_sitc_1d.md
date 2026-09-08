---
type: "Dataset"
title: "OpenDOSM Monthly Trade by SITC Section"
description: "DataPulse projection of OpenDOSM Monthly Trade by SITC Section from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/trade/trade_sitc_1d.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/trade/trade_sitc_1d.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_trade_sitc_1d.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Monthly Trade by SITC Section is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:e72ea956b5e941752da55722153202c61c90f80b9ee997f448453dd531ddb4b1`
- `record_count`: `3509`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_trade_sitc_1d.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
