---
type: "Dataset"
title: "Monthly Electricity Consumption"
description: "DataPulse projection of Monthly Electricity Consumption from Tenaga Nasional Berhad."
resource: "https://api.data.gov.my/data-catalogue?id=electricity_consumption"
tags: ["data.gov.my (OpenAPI)","non-vertical","monthly"]
sources:
  - {"id": "tnb","resource": "https://api.data.gov.my/data-catalogue?id=electricity_consumption","title": "Tenaga Nasional Berhad"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Tenaga Nasional Berhad via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/electricity_consumption.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 468
stale_after: "2024-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Electricity Consumption is published by Tenaga Nasional Berhad and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:53c70037b1df258ba178457b69d82f02c8ae261957a260b7603415e81a591ec3`
- `record_count`: `468`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/electricity_consumption.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
