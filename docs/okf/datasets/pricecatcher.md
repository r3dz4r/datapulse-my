---
type: "Dataset"
title: "PriceCatcher (Grocery Prices)"
description: "DataPulse projection of PriceCatcher (Grocery Prices) from KPDN."
resource: "https://storage.data.gov.my/pricecatcher/pricecatcher_2026-09.parquet"
tags: ["data.gov.my (KPDN)","non-vertical","monthly"]
sources:
  - {"id": "kpdn","resource": "https://storage.data.gov.my/pricecatcher/pricecatcher_2026-09.parquet","title": "KPDN"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "KPDN Malaysia via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/pricecatcher.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-10-20T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

PriceCatcher (Grocery Prices) is published by KPDN and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `record_count`: `1573`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/pricecatcher.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
