---
type: "Dataset"
title: "Monthly Trade by SITC Section (1 digit)"
description: "DataPulse projection of Monthly Trade by SITC Section (1 digit) from dosm."
resource: "https://api.data.gov.my/data-catalogue?id=trade_sitc_1d"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=trade_sitc_1d","title": "dosm"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-13T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-10-24T12:04:39Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Data source: Department of Statistics Malaysia"
datapulse:real_status: "degraded"
datapulse:health_report: "/data/trade_sitc_1d.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-10-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Trade by SITC Section (1 digit) is published by dosm and tracked by DataPulse. The latest published probe classifies it as `degraded`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:4925eeacbd88e7f40d4f29c7518f078b4410e9a07b0901da66223f53bc87823a`
- `record_count`: `4851`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/trade_sitc_1d.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
