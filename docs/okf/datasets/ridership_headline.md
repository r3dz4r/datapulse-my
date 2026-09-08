---
type: "Dataset"
title: "data.gov.my Daily Public Transport Ridership"
description: "DataPulse projection of data.gov.my Daily Public Transport Ridership from Ministry of Transport Malaysia and public transport operators."
resource: "https://storage.data.gov.my/transportation/ridership_headline.csv"
tags: ["data.gov.my (storage.data.gov.my)","non-vertical","daily"]
sources:
  - {"id": "mot","resource": "https://storage.data.gov.my/transportation/ridership_headline.csv","title": "Ministry of Transport Malaysia and public transport operators"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Prasarana, KTMB, and Ministry of Transport Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/ridership_headline.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-08-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

data.gov.my Daily Public Transport Ridership is published by Ministry of Transport Malaysia and public transport operators and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `15`
- `first_row_hash`: `shape-v1:fd7d9738e74a846447abf985e96a7cb1fa7396f4ad7698d54025ef509411228f`
- `record_count`: `2769`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/ridership_headline.md). The probe is described by [the data_gov_my_storage attested computation](/computations/data-gov-my-storage.md).
