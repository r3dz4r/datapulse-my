---
type: "Dataset"
title: "Annual Currency in Circulation"
description: "DataPulse projection of Annual Currency in Circulation from Bank Negara Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=currency_in_circulation_annual"
tags: ["data.gov.my (OpenAPI)","non-vertical","annual"]
sources:
  - {"id": "bnm","resource": "https://api.data.gov.my/data-catalogue?id=currency_in_circulation_annual","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/currency_in_circulation_annual.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 969
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Currency in Circulation is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:e7f213c386e51bdaa4e950d9b7c4897f587214f74fd90ab922c0452fd3542be6`
- `record_count`: `969`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/currency_in_circulation_annual.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
