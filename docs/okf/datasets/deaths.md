---
type: "Dataset"
title: "Annual Deaths"
description: "DataPulse projection of Annual Deaths from National Registration Department."
resource: "https://api.data.gov.my/data-catalogue?id=deaths"
tags: ["data.gov.my (OpenAPI)","non-vertical","annual"]
sources:
  - {"id": "jpn","resource": "https://api.data.gov.my/data-catalogue?id=deaths","title": "National Registration Department"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-11-05T03:33:57Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "National Registration Department, Department of Statistics Malaysia"
datapulse:real_status: "aging"
datapulse:health_report: "/data/deaths.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 25
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Deaths is published by National Registration Department and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:b5592e54ceba1a0059e3d3c188331bac6c8c38f5d56661062aaa78543ec5f2ef`
- `record_count`: `26`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/deaths.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
