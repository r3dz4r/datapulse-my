---
type: "Dataset"
title: "OpenDOSM Annual Real GDP by State & Sector"
description: "DataPulse projection of OpenDOSM Annual Real GDP by State & Sector from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/gdp/gdp_state_real_supply.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/gdp/gdp_state_real_supply.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_gdp_state_real_supply.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Annual Real GDP by State & Sector is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:6086a029b149e1fc1b2864c59f3ce23bb5cd451341989ae631ac0bd430fd5224`
- `record_count`: `2163`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_gdp_state_real_supply.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
