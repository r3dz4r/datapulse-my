---
type: "Dataset"
title: "data.gov.my Annual Interest Rates"
description: "DataPulse projection of data.gov.my Annual Interest Rates from Bank Negara Malaysia."
resource: "https://storage.data.gov.my/finsector/interest_rates_annual.csv"
tags: ["data.gov.my (storage.data.gov.my)","non-vertical","annual"]
sources:
  - {"id": "bnm","resource": "https://storage.data.gov.my/finsector/interest_rates_annual.csv","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Bank Negara Malaysia via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/dgm_interest_rates_annual.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
---

# Summary

data.gov.my Annual Interest Rates is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:f15a72621662bb8115156b0324aa5daaf367e452aac851b2d5dfee9a459419d3`
- `record_count`: `707`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dgm_interest_rates_annual.md). The probe is described by [the data_gov_my_storage attested computation](/computations/data-gov-my-storage.md).
