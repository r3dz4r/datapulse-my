---
type: "Dataset"
title: "Air Pollutant Concentrations"
description: "DataPulse projection of Air Pollutant Concentrations from Department of Environment Malaysia."
resource: "https://storage.data.gov.my/environment/air_pollution.csv"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "doe","resource": "https://storage.data.gov.my/environment/air_pollution.csv","title": "Department of Environment Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Environment Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/air_pollution.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 432
stale_after: "2023-01-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Air Pollutant Concentrations is published by Department of Environment Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:d39e0178df20c729a71a0d03702a731f1a15362f59b764e86677132d38f883db`
- `record_count`: `432`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/air_pollution.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
