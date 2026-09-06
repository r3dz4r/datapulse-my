---
type: "Dataset"
title: "Kuala Lumpur USD/MYR Reference Rate"
description: "DataPulse projection of Kuala Lumpur USD/MYR Reference Rate from Bank Negara Malaysia."
resource: "https://api.bnm.gov.my/public/kl-usd-reference-rate"
tags: ["BNM Open API (apikijangportal.bnm.gov.my)","non-vertical","daily (weekdays)"]
sources:
  - {"id": "bnm","resource": "https://api.bnm.gov.my/public/kl-usd-reference-rate","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T16:20:14Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via BNM Open API"
datapulse:real_status: "aging"
datapulse:health_report: "/data/bnm_kl_usd_myr.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 2
stale_after: "2026-09-07T00:00:00Z"
datapulse:stale_after_basis: "weekday_cadence"
---

# Summary

Kuala Lumpur USD/MYR Reference Rate is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `record_count`: `2`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_kl_usd_myr.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
