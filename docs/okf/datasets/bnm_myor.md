---
type: "Dataset"
title: "Malaysia Overnight Rate (MYOR)"
description: "DataPulse projection of Malaysia Overnight Rate (MYOR) from Bank Negara Malaysia."
resource: "https://api.bnm.gov.my/public/my-overnight-rate"
tags: ["BNM Open API (apikijangportal.bnm.gov.my)","non-vertical","daily"]
sources:
  - {"id": "bnm","resource": "https://api.bnm.gov.my/public/my-overnight-rate","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via BNM Open API"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/bnm_myor.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 1
stale_after: "2026-09-08T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Malaysia Overnight Rate (MYOR) is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `8`
- `first_row_hash`: `shape-v1:e42cf47c3841aad22c4e97c748f9e6e40a3a1a5dca549a6547346e57673a6369`
- `record_count`: `1`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_myor.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
