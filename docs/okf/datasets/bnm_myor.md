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
  - {"by": "process:datapulse-health-timer","at": "2026-11-24T20:20:44Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Source: Bank Negara Malaysia"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/bnm_myor.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 1
stale_after: "2026-11-25T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Malaysia Overnight Rate (MYOR) is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `8`
- `first_row_hash`: `shape-v1:c00e60cb151708f2dbbe32ff29478a02d7059640ac80d8aeb29fc4bf98467318`
- `record_count`: `1`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_myor.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
