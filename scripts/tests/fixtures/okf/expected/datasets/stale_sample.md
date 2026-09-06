---
type: "Dataset"
title: "Stale Sample"
description: "DataPulse projection of Stale Sample from Other Agency."
resource: "https://example.test/stale"
tags: ["sample-source","non-vertical","monthly"]
sources:
  - {"id": "other-agency","resource": "https://example.test/stale","title": "Other Agency"}
generated: {"by": "process:datapulse-pipeline","at": "2026-01-01T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-01T12:00:00Z"}
status: "stable"
datapulse:licence: "Open Government Licence"
datapulse:attribution: "Other Agency"
datapulse:real_status: "stale"
datapulse:health_report: "/data/stale_sample.md"
datapulse:methodology_version: null
datapulse:expected_record_count: 6
stale_after: "2026-02-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Stale Sample is published by Other Agency and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `record_count`: `6`

# Quirks

Published source has not refreshed.

# Health

See the [published health report](/data/stale_sample.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
