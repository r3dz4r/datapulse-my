---
type: "Dataset"
title: "Vehicle Registration Transactions"
description: "DataPulse projection of Vehicle Registration Transactions from Road Transport Department Malaysia and Ministry of Transport."
resource: "https://storage.data.gov.my/transportation/vehicles_2026.csv"
tags: ["data.gov.my (storage)","non-vertical","daily"]
sources:
  - {"id": "jpj","resource": "https://storage.data.gov.my/transportation/vehicles_2026.csv","title": "Road Transport Department Malaysia and Ministry of Transport"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Road Transport Department Malaysia and Ministry of Transport via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/registration_transactions_all.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 827353
stale_after: "2026-08-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Vehicle Registration Transactions is published by Road Transport Department Malaysia and Ministry of Transport and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:81aae8f319997af4bdb4092d46492539c0ffcbbd77f18b3794574352709a6650`
- `record_count`: `987887`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/registration_transactions_all.md). The probe is described by [the data_gov_my_archive attested computation](/computations/data-gov-my-archive.md).
