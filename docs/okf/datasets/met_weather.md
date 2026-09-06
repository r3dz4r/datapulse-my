---
type: "Dataset"
title: "MET Malaysia Weather Forecast"
description: "DataPulse projection of MET Malaysia Weather Forecast from MET Malaysia."
resource: "https://api.data.gov.my/weather/forecast"
tags: ["data.gov.my (MET Malaysia)","non-vertical","daily"]
sources:
  - {"id": "met","resource": "https://api.data.gov.my/weather/forecast","title": "MET Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "MET Malaysia via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/met_weather.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 2520
stale_after: "2026-09-07T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

MET Malaysia Weather Forecast is published by MET Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `9`
- `first_row_hash`: `shape-v1:645ed633e9cd59951656d6162c9ba466a6687d04af54d5e516c6d484a0989c7a`
- `record_count`: `3101`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/met_weather.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
