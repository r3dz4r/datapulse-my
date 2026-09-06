---
type: "Dataset"
title: "Car Registration Transactions"
description: "DataPulse projection of Car Registration Transactions from Road Transport Department Malaysia and Ministry of Transport."
resource: "https://storage.data.gov.my/transportation/cars_2026.csv"
tags: ["data.gov.my (storage)","non-vertical","daily"]
sources:
  - {"id": "jpj","resource": "https://storage.data.gov.my/transportation/cars_2026.csv","title": "Road Transport Department Malaysia and Ministry of Transport"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Road Transport Department Malaysia and Ministry of Transport via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/registration_transactions_car.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-08-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Car Registration Transactions is published by Road Transport Department Malaysia and Ministry of Transport and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `7`
- `first_row_hash`: `shape-v1:c5d469913620c08a8848cf11086f32f5d601310db31135c22d8250ae37247d1c`
- `record_count`: `489340`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/registration_transactions_car.md). The probe is described by [the data_gov_my_archive attested computation](/computations/data-gov-my-archive.md).
