---
type: "Dataset"
title: "data.gov.my Monthly Payment Instruments"
description: "DataPulse projection of data.gov.my Monthly Payment Instruments from Bank Negara Malaysia."
resource: "https://storage.data.gov.my/finsector/payments/instruments.csv"
tags: ["data.gov.my (storage.data.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://storage.data.gov.my/finsector/payments/instruments.csv","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dgm_payments_instruments.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

data.gov.my Monthly Payment Instruments is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:6a1d131659dcb4e7f44163dc49d8a3e7a4f6e1deacbf5f2fda067c83d0fe35bc`
- `record_count`: `720`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dgm_payments_instruments.md). The probe is described by [the data_gov_my_storage attested computation](/computations/data-gov-my-storage.md).
