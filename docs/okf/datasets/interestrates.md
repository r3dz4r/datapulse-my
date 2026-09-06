---
type: "Dataset"
title: "Monthly Interest Rates"
description: "DataPulse projection of Monthly Interest Rates from Bank Negara Malaysia."
resource: "https://storage.data.gov.my/finsector/interest_rates.csv"
tags: ["data.gov.my","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://storage.data.gov.my/finsector/interest_rates.csv","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/interestrates.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 5664
stale_after: "2026-07-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Interest Rates is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:f15a72621662bb8115156b0324aa5daaf367e452aac851b2d5dfee9a459419d3`
- `record_count`: `5808`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/interestrates.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
