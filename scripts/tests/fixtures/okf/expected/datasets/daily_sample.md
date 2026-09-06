---
type: "Dataset"
title: "Daily Sample"
description: "DataPulse projection of Daily Sample from Sample Agency."
resource: "https://example.test/daily"
tags: ["sample-source","vertical","daily (weekdays)"]
sources:
  - {"id": "sample-agency","resource": "https://example.test/daily","title": "Sample Agency","last_modified": "2026-09-01T00:00:00Z"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-01T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-01T12:00:00Z"}
status: "stable"
datapulse:licence: "Open Government Licence"
datapulse:attribution: "Sample Agency"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/daily_sample.md"
datapulse:methodology_version: null
datapulse:expected_record_count: 4
stale_after: "2026-09-02T00:00:00Z"
datapulse:stale_after_basis: "weekday_cadence"
---

# Summary

Daily Sample is published by Sample Agency and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `schema_fingerprint`: `sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
- `column_count`: `2`
- `record_count`: `4`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/daily_sample.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
