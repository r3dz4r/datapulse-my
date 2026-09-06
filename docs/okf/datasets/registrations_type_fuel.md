---
type: "Dataset"
title: "Monthly Vehicle Registrations by Vehicle and Fuel Type"
description: "DataPulse projection of Monthly Vehicle Registrations by Vehicle and Fuel Type from Road Transport Department Malaysia and Ministry of Transport."
resource: "https://api.data.gov.my/data-catalogue?id=registrations_type_fuel"
tags: ["data.gov.my (OpenAPI)","non-vertical","monthly"]
sources:
  - {"id": "jpj","resource": "https://api.data.gov.my/data-catalogue?id=registrations_type_fuel","title": "Road Transport Department Malaysia and Ministry of Transport"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Road Transport Department Malaysia and Ministry of Transport via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/registrations_type_fuel.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 10000
stale_after: "2026-08-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Vehicle Registrations by Vehicle and Fuel Type is published by Road Transport Department Malaysia and Ministry of Transport and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:6fa57a8cbb22571d9f1f4c2a53ffb91a9bd8dc18e0692d19da7c0725d04db097`
- `record_count`: `10801`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/registrations_type_fuel.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
