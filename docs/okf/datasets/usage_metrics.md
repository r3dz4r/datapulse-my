---
type: "Dataset"
title: "Daily Usage Metrics for data.gov.my"
description: "DataPulse projection of Daily Usage Metrics for data.gov.my from National Digital Department and Ministry of Digital."
resource: "https://api.data.gov.my/data-catalogue?id=usage_metrics"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "jdn","resource": "https://api.data.gov.my/data-catalogue?id=usage_metrics","title": "National Digital Department and Ministry of Digital"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "National Digital Department and Ministry of Digital via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/usage_metrics.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 1055
stale_after: "2026-09-07T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Daily Usage Metrics for data.gov.my is published by National Digital Department and Ministry of Digital and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:5d8c7ee765aefe45f6124f8dd4ecfef903d2616d6a0d9ea25dac47a6b0866405`
- `record_count`: `1086`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/usage_metrics.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
