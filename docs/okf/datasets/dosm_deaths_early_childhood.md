---
type: "Dataset"
title: "Annual Early Childhood Deaths"
description: "DataPulse projection of Annual Early Childhood Deaths from National Registration Department and Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=deaths_early_childhood"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "jpn","resource": "https://api.data.gov.my/data-catalogue?id=deaths_early_childhood","title": "National Registration Department and Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "National Registration Department and Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_deaths_early_childhood.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 125
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Early Childhood Deaths is published by National Registration Department and Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:6d6f7487822021855460f385ca2a1e0cd906a13c7242be602d7db1013e17c6a2`
- `record_count`: `125`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_deaths_early_childhood.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
