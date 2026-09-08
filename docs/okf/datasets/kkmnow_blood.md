---
type: "Dataset"
title: "KKMNOW Daily Blood Donations and Stock"
description: "DataPulse projection of KKMNOW Daily Blood Donations and Stock from Ministry of Health Malaysia."
resource: "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/blood_01_stock_timeseries.parquet"
tags: ["github.com/MoH-Malaysia/kkmnow-data","non-vertical","daily"]
sources:
  - {"id": "kkm","resource": "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/blood_01_stock_timeseries.parquet","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "MIT License"
datapulse:attribution: "Ministry of Health Malaysia via GitHub kkmnow-data"
datapulse:real_status: "stale"
datapulse:health_report: "/data/kkmnow_blood.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2022-10-27T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

KKMNOW Daily Blood Donations and Stock is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `record_count`: `133`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/kkmnow_blood.md). The probe is described by [the github_parquet attested computation](/computations/github-parquet.md).
