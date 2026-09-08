---
type: "Dataset"
title: "Number of Datasets on data.gov.my"
description: "DataPulse projection of Number of Datasets on data.gov.my from National Digital Department and Ministry of Digital."
resource: "https://api.data.gov.my/data-catalogue?id=metrics_content"
tags: ["data.gov.my (OpenAPI)","non-vertical","monthly"]
sources:
  - {"id": "jdn","resource": "https://api.data.gov.my/data-catalogue?id=metrics_content","title": "National Digital Department and Ministry of Digital"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "National Digital Department and Ministry of Digital via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/metrics_content.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 36
stale_after: "2026-10-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Number of Datasets on data.gov.my is published by National Digital Department and Ministry of Digital and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:ac1ca2e75f47ae51d142f03a6995ea7391cbdf757a5e9c4537e574daec9fbdfb`
- `record_count`: `37`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/metrics_content.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
