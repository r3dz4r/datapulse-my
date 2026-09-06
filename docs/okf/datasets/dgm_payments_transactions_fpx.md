---
type: "Dataset"
title: "data.gov.my Daily FPX Transactions"
description: "DataPulse projection of data.gov.my Daily FPX Transactions from Bank Negara Malaysia."
resource: "https://storage.data.gov.my/finsector/payments/trnsc_daily_fpx.csv"
tags: ["data.gov.my (storage.data.gov.my)","non-vertical","daily"]
sources:
  - {"id": "bnm","resource": "https://storage.data.gov.my/finsector/payments/trnsc_daily_fpx.csv","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dgm_payments_transactions_fpx.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
---

# Summary

data.gov.my Daily FPX Transactions is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:a434dc5f75dbcb949e85278c16502c19f09f75381d4176390546e2ae92fd91d0`
- `record_count`: `7302`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dgm_payments_transactions_fpx.md). The probe is described by [the data_gov_my_storage attested computation](/computations/data-gov-my-storage.md).
