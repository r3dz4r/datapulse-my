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
  - {"by": "process:datapulse-health-timer","at": "2026-10-29T11:51:41Z"}
status: "stable"
datapulse:licence: "Singapore Open Data Licence v1.0 (attribution required)"
datapulse:attribution: "Contains information from National Environment Agency, Singapore Open Data Licence v1.0; accessed 2026-09-07"
datapulse:real_status: "degraded"
datapulse:health_report: "/data/sg_datagov_weather_readings.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-10-30T23:45:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Weather Readings real-time (SG) is published by Singapore Government and tracked by DataPulse. The latest published probe classifies it as `degraded`.

# Schema

- `column_count`: `2`
- `first_row_hash`: `shape-v1:ff460652b5269c9d7dc04f0703c8babd6d9021aa520bc059edd2f2a356923c9c`
- `record_count`: `1`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/sg_datagov_weather_readings.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
