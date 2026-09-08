---
type: "Dataset"
title: "KKMNOW Weekly COVID-19 Epidemiological Surveillance"
description: "DataPulse projection of KKMNOW Weekly COVID-19 Epidemiological Surveillance from Ministry of Health Malaysia."
resource: "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/covidepid_01_util.parquet"
tags: ["github.com/MoH-Malaysia/kkmnow-data","non-vertical","weekly"]
sources:
  - {"id": "kkm","resource": "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/covidepid_01_util.parquet","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "MIT License"
datapulse:attribution: "Ministry of Health Malaysia via GitHub kkmnow-data"
datapulse:real_status: "unknown-freshness"
datapulse:health_report: "/data/kkmnow_covidepid.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
---

# Summary

KKMNOW Weekly COVID-19 Epidemiological Surveillance is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `unknown-freshness`.

# Schema

- `record_count`: `47`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/kkmnow_covidepid.md). The probe is described by [the github_parquet attested computation](/computations/github-parquet.md).
