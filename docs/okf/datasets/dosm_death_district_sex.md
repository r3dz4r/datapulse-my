---
type: "Dataset"
title: "OpenDOSM Annual Deaths by District and Sex"
description: "DataPulse projection of OpenDOSM Annual Deaths by District and Sex from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/demography/death_district_sex.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/demography/death_district_sex.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_death_district_sex.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Annual Deaths by District and Sex is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:f785f7a345c0903b19e2fee5ec337e377676c7fe0eebc5af42a948ff5857944e`
- `record_count`: `2361`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_death_district_sex.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
