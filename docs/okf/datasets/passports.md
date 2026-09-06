---
type: "Dataset"
title: "Monthly Passport Issuances by State and Branch"
description: "DataPulse projection of Monthly Passport Issuances by State and Branch from Immigration Department of Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=passports"
tags: ["data.gov.my (OpenAPI)","non-vertical","monthly"]
sources:
  - {"id": "immigration","resource": "https://api.data.gov.my/data-catalogue?id=passports","title": "Immigration Department of Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Immigration Department of Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/passports.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 5684
stale_after: "2024-11-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Monthly Passport Issuances by State and Branch is published by Immigration Department of Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:73cea601374018b9e40a37c318581d6f6df68905fc83ac0d229815620d94facc`
- `record_count`: `5684`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/passports.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
