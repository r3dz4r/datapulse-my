---
type: "Dataset"
title: "Annual Population by Parliamentary Constituency"
description: "DataPulse projection of Annual Population by Parliamentary Constituency from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/population/population_parlimen.csv"
tags: ["OpenDOSM (also indexed by data.gov.my)","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/population/population_parlimen.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/population_parlimen.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 5550
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Population by Parliamentary Constituency is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `7`
- `first_row_hash`: `shape-v1:7bdd50deeea70345ac0620338e7d214526bd83885ce025227e768cb3ea6dddd3`
- `record_count`: `5550`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/population_parlimen.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
