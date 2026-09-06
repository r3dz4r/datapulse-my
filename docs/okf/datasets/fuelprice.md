---
type: "Dataset"
title: "Malaysian Fuel Prices"
description: "DataPulse projection of Malaysian Fuel Prices from Ministry of Finance Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=fuelprice"
tags: ["data.gov.my","non-vertical","weekly"]
sources:
  - {"id": "mof","resource": "https://api.data.gov.my/data-catalogue?id=fuelprice","title": "Ministry of Finance Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Ministry of Finance Malaysia via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/fuelprice.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 945
stale_after: "2026-09-13T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Malaysian Fuel Prices is published by Ministry of Finance Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `10`
- `first_row_hash`: `shape-v1:94187a8617d321c5a0b27112029defe7a7bdbe21be8fe3986ee3c10e18ad7bb9`
- `record_count`: `953`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/fuelprice.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
