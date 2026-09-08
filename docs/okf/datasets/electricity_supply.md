---
type: "Dataset"
title: "data.gov.my Electricity Supply"
description: "DataPulse projection of data.gov.my Electricity Supply from Energy Commission and electricity utilities."
resource: "https://storage.data.gov.my/energy/electricity_supply.csv"
tags: ["data.gov.my (storage.data.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "energy_commission","resource": "https://storage.data.gov.my/energy/electricity_supply.csv","title": "Energy Commission and electricity utilities"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Energy Commission, DOSM, and Malaysian electricity utilities via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/electricity_supply.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2024-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

data.gov.my Electricity Supply is published by Energy Commission and electricity utilities and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:5d93c3e8a1025f6172ab70688a956373a8d5e77160603b23aef7aa9f4fc7fae8`
- `record_count`: `468`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/electricity_supply.md). The probe is described by [the data_gov_my_storage attested computation](/computations/data-gov-my-storage.md).
