---
type: "Dataset"
title: "Monthly Currency in Circulation"
description: "DataPulse projection of Monthly Currency in Circulation from Bank Negara Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=currency_in_circulation"
tags: ["data.gov.my (OpenAPI)","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://api.data.gov.my/data-catalogue?id=currency_in_circulation","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/currency_in_circulation.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 5928
stale_after: "2026-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Currency in Circulation is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:e7f213c386e51bdaa4e950d9b7c4897f587214f74fd90ab922c0452fd3542be6`
- `record_count`: `6042`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/currency_in_circulation.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
