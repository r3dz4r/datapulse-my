---
type: "Dataset"
title: "Monthly Monetary Aggregates"
description: "DataPulse projection of Monthly Monetary Aggregates from Bank Negara Malaysia."
resource: "https://storage.data.gov.my/finsector/money_aggregates.csv"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://storage.data.gov.my/finsector/money_aggregates.csv","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/monetary_aggregates.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 1872
stale_after: "2026-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Monetary Aggregates is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:444b6a930292036e6e641353f35404769c2acc7f9127293974020b10177ae128`
- `record_count`: `1944`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/monetary_aggregates.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
