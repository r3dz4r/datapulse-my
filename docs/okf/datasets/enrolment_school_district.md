---
type: "Dataset"
title: "Enrolment in Government Schools by District"
description: "DataPulse projection of Enrolment in Government Schools by District from Ministry of Education Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=enrolment_school_district"
tags: ["data.gov.my (OpenAPI)","non-vertical","annual"]
sources:
  - {"id": "moe","resource": "https://api.data.gov.my/data-catalogue?id=enrolment_school_district","title": "Ministry of Education Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Ministry of Education Malaysia via data.gov.my"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/enrolment_school_district.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 10000
stale_after: "2026-12-29T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Enrolment in Government Schools by District is published by Ministry of Education Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:71815861b22b1204a6cf92da98579eaeace2831b6baecacede0209a719a09a87`
- `record_count`: `12756`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/enrolment_school_district.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
