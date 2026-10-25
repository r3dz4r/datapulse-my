---
type: "Dataset"
title: "Water Consumption by State and Sector"
description: "DataPulse projection of Water Consumption by State and Sector from National Water Services Commission."
resource: "https://api.data.gov.my/data-catalogue?id=water_consumption"
tags: ["data.gov.my (OpenAPI)","non-vertical","annual"]
sources:
  - {"id": "span","resource": "https://api.data.gov.my/data-catalogue?id=water_consumption","title": "National Water Services Commission"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-10-05T06:46:30Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "The National Water Services Commission, Ministry of Natural Resources & Environmental Sustainability, Department of Statistics Malaysia"
datapulse:real_status: "aging"
datapulse:health_report: "/data/water_consumption.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 600
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Water Consumption by State and Sector is published by National Water Services Commission and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:572e06aca0d31596c460f13ea8844fb0f5ddb6be891c6fc3c8d4d80526bbb52f`
- `record_count`: `660`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/water_consumption.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
