---
type: "Dataset"
title: "Monthly Exchange Rates"
description: "DataPulse projection of Monthly Exchange Rates from Bank Negara Malaysia."
resource: "https://storage.data.gov.my/finsector/exr/monthly.csv"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://storage.data.gov.my/finsector/exr/monthly.csv","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/exchangerates.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 1755
stale_after: "2026-04-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Exchange Rates is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `29`
- `first_row_hash`: `shape-v1:d4c1658a2c3b6c63c02aee9e3d9cba075d82346de5496b57c31b1bf211fe1825`
- `record_count`: `1755`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/exchangerates.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
