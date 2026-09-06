---
type: "Dataset"
title: "OpenDOSM Monthly Trade by End Use (BEC)"
description: "DataPulse projection of OpenDOSM Monthly Trade by End Use (BEC) from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/trade/trade_enduse_bec.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/trade/trade_enduse_bec.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dosm_trade_enduse_bec.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Monthly Trade by End Use (BEC) is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:e5584ad6fa56f5dcae79f1592d79dcce7f4e9a54fd33daaf918e49c5c96e0e77`
- `record_count`: `14478`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_trade_enduse_bec.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
