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
  - {"by": "process:datapulse-health-timer","at": "2026-11-23T02:45:48Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Source: Bank Negara Malaysia"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/bnm_interest_rate.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 3
stale_after: "2027-01-05T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Interest Rates: Banking Institutions is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `8`
- `first_row_hash`: `shape-v1:d97483cc4a7c754b8c0f7028e87b21795f060f148af914f680dc051d79d3e8c7`
- `record_count`: `3`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_interest_rate.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
