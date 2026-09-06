---
type: "Dataset"
title: "Motorcycle Registration Transactions"
description: "DataPulse projection of Motorcycle Registration Transactions from Road Transport Department Malaysia and Ministry of Transport."
resource: "https://storage.data.gov.my/transportation/motorcycles_2026.csv"
tags: ["data.gov.my (storage)","non-vertical","daily"]
sources:
  - {"id": "jpj","resource": "https://storage.data.gov.my/transportation/motorcycles_2026.csv","title": "Road Transport Department Malaysia and Ministry of Transport"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Road Transport Department Malaysia and Ministry of Transport via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/registration_transactions_motorcycle.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-08-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Motorcycle Registration Transactions is published by Road Transport Department Malaysia and Ministry of Transport and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:902ecd84e9de260b93a668d9ff077d2c7ec3a587d7b2bd6d75d371fcb4bf9a6b`
- `record_count`: `466158`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/registration_transactions_motorcycle.md). The probe is described by [the data_gov_my_archive attested computation](/computations/data-gov-my-archive.md).
