---
type: "Dataset"
title: "Monthly Payment Channels"
description: "DataPulse projection of Monthly Payment Channels from Bank Negara Malaysia."
resource: "https://storage.data.gov.my/finsector/payments/channels.csv"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://storage.data.gov.my/finsector/payments/channels.csv","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/payment_channels.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 430
stale_after: "2026-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Payment Channels is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:7ee50d25d9338ca0ded0584603a850b7d3ddbe51e576cdfc04ee56e40c18b964`
- `record_count`: `450`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/payment_channels.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
