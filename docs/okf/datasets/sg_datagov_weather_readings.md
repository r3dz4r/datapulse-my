---
type: "Dataset"
title: "Weather Readings real-time (SG)"
description: "DataPulse projection of Weather Readings real-time (SG) from Singapore Government."
resource: "https://api.data.gov.sg/v1/environment/air-temperature"
tags: ["data.gov.sg","non-vertical","daily"]
sources:
  - {"id": "sg-datagov","resource": "https://api.data.gov.sg/v1/environment/air-temperature","title": "Singapore Government"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-07T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-08T00:31:24Z"}
status: "stable"
datapulse:licence: "Singapore Open Data Licence v1.0 (attribution required)"
datapulse:attribution: "Contains information from National Environment Agency, Singapore Open Data Licence v1.0"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/sg_datagov_weather_readings.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-09-09T12:25:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Weather Readings real-time (SG) is published by Singapore Government and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `2`
- `first_row_hash`: `shape-v1:f0a5d8e8806c818fa057d025c7f656d4e159e9607a8128856c444455f5dba781`
- `record_count`: `1`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/sg_datagov_weather_readings.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
