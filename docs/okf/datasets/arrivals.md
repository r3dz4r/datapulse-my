---
type: "Dataset"
title: "Monthly Arrivals by Nationality & Sex"
description: "DataPulse projection of Monthly Arrivals by Nationality & Sex from Immigration Department of Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=arrivals"
tags: ["data.gov.my (OpenAPI)","non-vertical","monthly"]
sources:
  - {"id": "immigration","resource": "https://api.data.gov.my/data-catalogue?id=arrivals","title": "Immigration Department of Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Immigration Department of Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/arrivals.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 10000
stale_after: "2024-11-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Arrivals by Nationality & Sex is published by Immigration Department of Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:144e6b77ddb17df3f1ebd8a36abaf91ed2add355468b4eb41873bc9e1d743600`
- `record_count`: `13050`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/arrivals.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
