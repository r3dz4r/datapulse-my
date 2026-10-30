---
type: "Dataset"
title: "Interbank Swap"
description: "DataPulse projection of Interbank Swap from Bank Negara Malaysia."
resource: "https://api.bnm.gov.my/public/interbank-swap"
tags: ["BNM Open API (apikijangportal.bnm.gov.my)","non-vertical","daily (weekdays)"]
sources:
  - {"id": "bnm","resource": "https://api.bnm.gov.my/public/interbank-swap","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-10-29T11:51:41Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Source: Bank Negara Malaysia"
datapulse:real_status: "degraded"
datapulse:health_report: "/data/bnm_interbank_swap.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 2
stale_after: "2026-10-30T00:00:00Z"
datapulse:stale_after_basis: "weekday_cadence"
---

# Summary

Interbank Swap is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `degraded`.

# Schema

- `first_row_hash`: `shape-v1:16b3d676d9f2b6cecf37f15202ee0f4f94b06a7f719e95a0cc8cb4dc206b4105`
- `record_count`: `2`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_interbank_swap.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
