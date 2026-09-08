---
type: "Dataset"
title: "OpenDOSM Annual Real GDP by Supply Sector"
description: "DataPulse projection of OpenDOSM Annual Real GDP by Supply Sector from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/gdp/gdp_annual_real_supply.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/gdp/gdp_annual_real_supply.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_gdp_annual_real_supply.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Annual Real GDP by Supply Sector is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:69b57252740ad034b05c61036fed5088d0402b198a91be62fb31814fbec60344`
- `record_count`: `147`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_gdp_annual_real_supply.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
