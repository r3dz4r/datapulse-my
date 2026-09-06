---
type: "Dataset"
title: "Crop Area by District"
description: "DataPulse projection of Crop Area by District from Department of Agriculture and Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=crops_district_area"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "doa","resource": "https://api.data.gov.my/data-catalogue?id=crops_district_area","title": "Department of Agriculture and Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Agriculture and Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dosm_crops_district_area.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 10000
stale_after: "2018-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Crop Area by District is published by Department of Agriculture and Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:63178b0cb11835d39e9a854227e001ef45bbf6bfda6ce7f4961ca2a6e4a5dfa0`
- `record_count`: `10555`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_crops_district_area.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
