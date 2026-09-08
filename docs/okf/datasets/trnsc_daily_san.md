---
type: "Dataset"
title: "Daily Shared ATM Network (SAN) Transactions"
description: "DataPulse projection of Daily Shared ATM Network (SAN) Transactions from Payments Network Malaysia and Bank Negara Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=trnsc_daily_san"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "paynet","resource": "https://api.data.gov.my/data-catalogue?id=trnsc_daily_san","title": "Payments Network Malaysia and Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Payments Network Malaysia and Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/trnsc_daily_san.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 7213
stale_after: "2026-09-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Daily Shared ATM Network (SAN) Transactions is published by Payments Network Malaysia and Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:eeadf31f118e6d5638bdb7130033424044985406a4f786af0cd0716de1f25301`
- `record_count`: `7297`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/trnsc_daily_san.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
