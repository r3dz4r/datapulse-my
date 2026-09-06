---
type: "Dataset"
title: "KKMNOW Healthcare Resources/Facilities Directory"
description: "DataPulse projection of KKMNOW Healthcare Resources/Facilities Directory from Ministry of Health Malaysia."
resource: "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/facilities_01_table.parquet"
tags: ["github.com/MoH-Malaysia/kkmnow-data","non-vertical","annual"]
sources:
  - {"id": "kkm","resource": "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/facilities_01_table.parquet","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "MIT License"
datapulse:attribution: "Ministry of Health Malaysia via GitHub kkmnow-data"
datapulse:real_status: "unknown-freshness"
datapulse:health_report: "/data/kkmnow_facilities.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
---

# Summary

KKMNOW Healthcare Resources/Facilities Directory is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `unknown-freshness`.

# Schema

- `record_count`: `1244`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/kkmnow_facilities.md). The probe is described by [the github_parquet attested computation](/computations/github-parquet.md).
