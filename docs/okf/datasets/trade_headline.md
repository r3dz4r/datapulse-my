---
type: "Dataset"
title: "OpenDOSM Monthly Trade Headline"
description: "DataPulse projection of OpenDOSM Monthly Trade Headline from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/trade/trade_headline.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/trade/trade_headline.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "stale"
datapulse:health_report: "/data/trade_headline.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-05-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Monthly Trade Headline is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `9`
- `first_row_hash`: `shape-v1:20325e769ff9f44b37dce25d09b4840dea747e663d1c8c7367d0c42cdf0c494c`
- `record_count`: `743`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/trade_headline.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
