---
type: "Dataset"
title: "KKMNOW PeKa B40 Daily Health Screenings by State"
description: "DataPulse projection of KKMNOW PeKa B40 Daily Health Screenings by State from Ministry of Health Malaysia."
resource: "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/pekab40_01_timeseries.parquet"
tags: ["github.com/MoH-Malaysia/kkmnow-data","non-vertical","daily"]
sources:
  - {"id": "kkm","resource": "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/pekab40_01_timeseries.parquet","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "MIT License"
datapulse:attribution: "Ministry of Health Malaysia via GitHub kkmnow-data"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/kkmnow_pekab40.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-09-07T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

KKMNOW PeKa B40 Daily Health Screenings by State is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `record_count`: `1211`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/kkmnow_pekab40.md). The probe is described by [the github_parquet attested computation](/computations/github-parquet.md).
