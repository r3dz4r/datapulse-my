---
type: "Dataset"
title: "Annual Stillbirths"
description: "DataPulse projection of Annual Stillbirths from Ministry of Health and Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=stillbirths"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "kkm","resource": "https://api.data.gov.my/data-catalogue?id=stillbirths","title": "Ministry of Health and Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Ministry of Health and Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_stillbirths.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 25
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Stillbirths is published by Ministry of Health and Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:b5592e54ceba1a0059e3d3c188331bac6c8c38f5d56661062aaa78543ec5f2ef`
- `record_count`: `25`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_stillbirths.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
