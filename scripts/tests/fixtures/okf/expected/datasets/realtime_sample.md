---
type: "Dataset"
title: "Realtime Sample"
description: "DataPulse projection of Realtime Sample from Sample Agency."
resource: "https://example.test/realtime"
tags: ["sample-source","non-vertical","30 seconds"]
sources:
  - {"id": "sample-agency","resource": "https://example.test/realtime","title": "Sample Agency"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-01T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-01T12:00:00Z"}
status: "stable"
datapulse:licence: "Open Government Licence"
datapulse:attribution: "Sample Agency"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/realtime_sample.md"
datapulse:methodology_version: null
datapulse:expected_record_count: 5
stale_after: "2026-09-01T12:10:00Z"
datapulse:stale_after_basis: "realtime"
---

# Summary

Realtime Sample is published by Sample Agency and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `record_count`: `5`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/realtime_sample.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
