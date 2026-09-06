---
type: "Dataset"
title: "SITC"
description: "DataPulse projection of SITC from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=sitc"
tags: ["DOSM via data.gov.my","non-vertical","as-required"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=sitc","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "reference"
datapulse:health_report: "/data/dosm_sitc.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 9
---

# Summary

SITC is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `reference`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:1e4d283e269511909ba612b987b9812824642657a1f00c16215a1f17142d8258`
- `record_count`: `9`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_sitc.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
