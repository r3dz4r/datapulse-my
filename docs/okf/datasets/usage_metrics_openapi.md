---
type: "Dataset"
title: "Daily OpenAPI Hits by Endpoint"
description: "DataPulse projection of Daily OpenAPI Hits by Endpoint from National Digital Department and Ministry of Digital."
resource: "https://api.data.gov.my/data-catalogue?id=usage_metrics_openapi"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "jdn","resource": "https://api.data.gov.my/data-catalogue?id=usage_metrics_openapi","title": "National Digital Department and Ministry of Digital"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "National Digital Department and Ministry of Digital via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/usage_metrics_openapi.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 10000
stale_after: "2026-09-06T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Daily OpenAPI Hits by Endpoint is published by National Digital Department and Ministry of Digital and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:d5df8abf7e9c872c8d891c1e3db178f5de0c461a175c3b6f080405b8176543e5`
- `record_count`: `18477`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/usage_metrics_openapi.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
