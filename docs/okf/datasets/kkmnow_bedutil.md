---
type: "Dataset"
title: "KKMNOW Hospital Bed Utilisation by Facility/State"
description: "DataPulse projection of KKMNOW Hospital Bed Utilisation by Facility/State from Ministry of Health Malaysia."
resource: "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/bedutil_01_table_facility.parquet"
tags: ["github.com/MoH-Malaysia/kkmnow-data","non-vertical","daily"]
sources:
  - {"id": "kkm","resource": "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/bedutil_01_table_facility.parquet","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "MIT License"
datapulse:attribution: "Ministry of Health Malaysia via GitHub kkmnow-data"
datapulse:real_status: "unknown-freshness"
datapulse:health_report: "/data/kkmnow_bedutil.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
---

# Summary

KKMNOW Hospital Bed Utilisation by Facility/State is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `unknown-freshness`.

# Schema

- `record_count`: `79`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/kkmnow_bedutil.md). The probe is described by [the github_parquet attested computation](/computations/github-parquet.md).
