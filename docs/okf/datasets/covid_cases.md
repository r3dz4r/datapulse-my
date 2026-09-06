---
type: "Dataset"
title: "Daily COVID-19 Cases by State"
description: "DataPulse projection of Daily COVID-19 Cases by State from Ministry of Health Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=covid_cases"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "kkm","resource": "https://api.data.gov.my/data-catalogue?id=covid_cases","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Ministry of Health Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/covid_cases.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 10000
stale_after: "2025-06-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Daily COVID-19 Cases by State is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `7`
- `first_row_hash`: `shape-v1:62c5a2aa9255178cc459c0a8c15ade5f21c1525d1167c94d889faf00b390c0e2`
- `record_count`: `33218`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/covid_cases.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
