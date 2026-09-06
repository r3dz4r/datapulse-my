---
type: "Dataset"
title: "Daily Live Births"
description: "DataPulse projection of Daily Live Births from National Registration Department."
resource: "https://api.data.gov.my/data-catalogue?id=births"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "jpn","resource": "https://api.data.gov.my/data-catalogue?id=births","title": "National Registration Department"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "National Registration Department via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/births.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 37833
stale_after: "2023-08-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Daily Live Births is published by National Registration Department and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:599eb878e879d8e98479e31359ffe8634bbf41817aad28e534f845a6bd3cb184`
- `record_count`: `37833`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/births.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
