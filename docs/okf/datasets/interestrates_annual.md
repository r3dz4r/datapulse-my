---
type: "Dataset"
title: "Annual Interest Rates"
description: "DataPulse projection of Annual Interest Rates from Bank Negara Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=interestrates_annual"
tags: ["data.gov.my (OpenAPI)","non-vertical","annual"]
sources:
  - {"id": "bnm","resource": "https://api.data.gov.my/data-catalogue?id=interestrates_annual","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/interestrates_annual.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 707
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Interest Rates is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:698d3772264303d1e69782f19770ae712ec40072d22cbbbcfb6c0a7068c7d7e7`
- `record_count`: `707`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/interestrates_annual.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
