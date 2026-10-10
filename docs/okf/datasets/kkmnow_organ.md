---
type: "Dataset"
title: "KKMNOW Organ Donation Pledges and Deaths"
description: "DataPulse projection of KKMNOW Organ Donation Pledges and Deaths from Ministry of Health Malaysia."
resource: "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/organ_01_timeseries.parquet"
tags: ["github.com/MoH-Malaysia/kkmnow-data","non-vertical","daily"]
sources:
  - {"id": "kkm","resource": "https://raw.githubusercontent.com/MoH-Malaysia/kkmnow-data/main/organ_01_timeseries.parquet","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-10-09T14:41:21Z"}
status: "stable"
datapulse:licence: "MIT License"
datapulse:attribution: "Source: Ministry of Health Malaysia (Kementerian Kesihatan Malaysia)"
datapulse:real_status: "stale"
datapulse:health_report: "/data/kkmnow_organ.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-09-30T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

KKMNOW Organ Donation Pledges and Deaths is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `record_count`: `1691`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/kkmnow_organ.md). The probe is described by [the github_parquet attested computation](/computations/github-parquet.md).
