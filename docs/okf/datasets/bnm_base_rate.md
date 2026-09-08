---
type: "Dataset"
title: "Base Rates / BLR / Effective LR"
description: "DataPulse projection of Base Rates / BLR / Effective LR from Bank Negara Malaysia."
resource: "https://api.bnm.gov.my/public/base-rate"
tags: ["BNM Open API (apikijangportal.bnm.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://api.bnm.gov.my/public/base-rate","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via BNM Open API"
datapulse:real_status: "stale"
datapulse:health_report: "/data/bnm_base_rate.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 12
stale_after: "2020-09-21T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Base Rates / BLR / Effective LR is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:b374c9c90e1aa3cd09487db74e6acce54051a4f286d093b5ef02f3c438b2f8aa`
- `record_count`: `35`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_base_rate.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
