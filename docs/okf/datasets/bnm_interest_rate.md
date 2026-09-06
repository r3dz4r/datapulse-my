---
type: "Dataset"
title: "Interest Rates: Banking Institutions"
description: "DataPulse projection of Interest Rates: Banking Institutions from Bank Negara Malaysia."
resource: "https://api.bnm.gov.my/public/interest-rate"
tags: ["BNM Open API (apikijangportal.bnm.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://api.bnm.gov.my/public/interest-rate","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via BNM Open API"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/bnm_interest_rate.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 3
stale_after: "2026-10-20T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Interest Rates: Banking Institutions is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `8`
- `first_row_hash`: `shape-v1:6f8ffe650be3f5da4ec5d9e7c6c5c5f4c78a921d6d46b94ae181263dd4e79ab1`
- `record_count`: `3`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_interest_rate.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
