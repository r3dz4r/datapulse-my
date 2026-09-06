---
type: "Dataset"
title: "Astronomy Almanac"
description: "DataPulse projection of Astronomy Almanac from Malaysian Meteorological Department."
resource: "https://api.data.gov.my/data-catalogue?id=almanak_astronomi"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "met","resource": "https://api.data.gov.my/data-catalogue?id=almanak_astronomi","title": "Malaysian Meteorological Department"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Malaysian Meteorological Department via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/almanak_astronomi.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 538
stale_after: "2026-09-05T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Astronomy Almanac is published by Malaysian Meteorological Department and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:3857068c199298de39c3e02f44c734cc4db70d8777dd2cf49e6c6d2569d90edc`
- `record_count`: `538`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/almanak_astronomi.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
