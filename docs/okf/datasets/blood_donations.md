---
type: "Dataset"
title: "Daily Blood Donations by Blood Group"
description: "DataPulse projection of Daily Blood Donations by Blood Group from National Blood Centre and Ministry of Health Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=blood_donations"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "national_blood_centre","resource": "https://api.data.gov.my/data-catalogue?id=blood_donations","title": "National Blood Centre and Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T05:22:25Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "National Blood Centre and Ministry of Health Malaysia via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/blood_donations.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 10000
stale_after: "2026-09-06T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Daily Blood Donations by Blood Group is published by National Blood Centre and Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:d03b0c9174a885656d7c0b69e9eed754073781d89ce0fd333378609089ad9bb2`
- `record_count`: `37765`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/blood_donations.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
