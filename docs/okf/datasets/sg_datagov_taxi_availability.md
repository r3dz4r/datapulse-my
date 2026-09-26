---
type: "Dataset"
title: "Taxi Availability real-time (SG)"
description: "DataPulse projection of Taxi Availability real-time (SG) from Singapore Government."
resource: "https://api.data.gov.sg/v1/transport/taxi-availability"
tags: ["data.gov.sg","non-vertical","daily"]
sources:
  - {"id": "sg-datagov","resource": "https://api.data.gov.sg/v1/transport/taxi-availability","title": "Singapore Government"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-07T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-26T02:55:29Z"}
status: "stable"
datapulse:licence: "Singapore Open Data Licence v1.0 (attribution required)"
datapulse:attribution: "Contains information from Land Transport Authority, Singapore Open Data Licence v1.0"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/sg_datagov_taxi_availability.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-09-27T14:55:19Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Taxi Availability real-time (SG) is published by Singapore Government and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `first_row_hash`: `shape-v1:5a6be641497ec1e2a986fdcb59e252b5cb587233b62a9939800540c3aec2ce07`
- `record_count`: `3`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/sg_datagov_taxi_availability.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
