---
type: "Dataset"
title: "Annual Deaths by District & Sex"
description: "DataPulse projection of Annual Deaths by District & Sex from National Registration Department and Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=deaths_district_sex"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "jpn","resource": "https://api.data.gov.my/data-catalogue?id=deaths_district_sex","title": "National Registration Department and Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "National Registration Department and Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_deaths_district_sex.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 2361
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Deaths by District & Sex is published by National Registration Department and Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:657baab564c51e55549d08cca67bdd95ca2daa82ad5f8e0ed493c7d1cd20bc56`
- `record_count`: `2361`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_deaths_district_sex.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
