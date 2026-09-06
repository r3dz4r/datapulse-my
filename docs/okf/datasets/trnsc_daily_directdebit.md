---
type: "Dataset"
title: "Daily DirectDebit Transactions"
description: "DataPulse projection of Daily DirectDebit Transactions from Payments Network Malaysia and Bank Negara Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=trnsc_daily_directdebit"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "paynet","resource": "https://api.data.gov.my/data-catalogue?id=trnsc_daily_directdebit","title": "Payments Network Malaysia and Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Payments Network Malaysia and Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/trnsc_daily_directdebit.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 1203
stale_after: "2026-09-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Daily DirectDebit Transactions is published by Payments Network Malaysia and Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:44548003c1b51e35d27dc7f574a6f33a8706abe8d2c5b8558a3250699558a4d6`
- `record_count`: `1221`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/trnsc_daily_directdebit.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
