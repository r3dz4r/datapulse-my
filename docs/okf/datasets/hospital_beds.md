---
type: "Dataset"
title: "Hospital Beds by State and Hospital Type"
description: "DataPulse projection of Hospital Beds by State and Hospital Type from Ministry of Health Malaysia."
resource: "https://storage.data.gov.my/healthcare/hospital_beds.csv"
tags: ["data.gov.my","non-vertical","annual"]
sources:
  - {"id": "kkm","resource": "https://storage.data.gov.my/healthcare/hospital_beds.csv","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-11-05T03:33:57Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Source: Ministry of Health Malaysia (Kementerian Kesihatan Malaysia)"
datapulse:real_status: "aging"
datapulse:health_report: "/data/hospital_beds.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 5468
stale_after: "2025-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Hospital Beds by State and Hospital Type is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:05567a1a5e876d211cb47ae0bbe79aa91104aefd00fdf7066ced9ddbc1259477`
- `record_count`: `6828`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/hospital_beds.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
