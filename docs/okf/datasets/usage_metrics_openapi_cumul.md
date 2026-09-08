---
type: "Dataset"
title: "Cumulative OpenAPI Hits by Endpoint"
description: "DataPulse projection of Cumulative OpenAPI Hits by Endpoint from National Digital Department and Ministry of Digital."
resource: "https://api.data.gov.my/data-catalogue?id=usage_metrics_openapi_cumul"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "jdn","resource": "https://api.data.gov.my/data-catalogue?id=usage_metrics_openapi_cumul","title": "National Digital Department and Ministry of Digital"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "National Digital Department and Ministry of Digital via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/usage_metrics_openapi_cumul.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 30
stale_after: "2026-09-07T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Cumulative OpenAPI Hits by Endpoint is published by National Digital Department and Ministry of Digital and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:06f320a2e4d2434d076b040e6f26ad0162a7c8339c06926ffc857890944a9a94`
- `record_count`: `30`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/usage_metrics_openapi_cumul.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
