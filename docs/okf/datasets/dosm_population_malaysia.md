---
type: "Dataset"
title: "OpenDOSM Annual Population, Malaysia"
description: "DataPulse projection of OpenDOSM Annual Population, Malaysia from Department of Statistics Malaysia."
resource: "https://storage.dosm.gov.my/population/population_malaysia.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/population/population_malaysia.csv","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/dosm_population_malaysia.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2027-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Annual Population, Malaysia is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:6b77430a05b624ff0efd950562c8b52f7fe88436227c9ab9c81b881f2796a469`
- `record_count`: `17814`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_population_malaysia.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
