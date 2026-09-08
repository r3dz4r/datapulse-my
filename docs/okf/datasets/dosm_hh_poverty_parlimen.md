---
type: "Dataset"
title: "Poverty by Parliament"
description: "DataPulse projection of Poverty by Parliament from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=hh_poverty_parlimen"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=hh_poverty_parlimen","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_hh_poverty_parlimen.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 666
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Poverty by Parliament is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:ee8831fc30a9489c9dc90129c92b6efe61640ca27190489a8020278cb612ae0f`
- `record_count`: `666`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_hh_poverty_parlimen.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
