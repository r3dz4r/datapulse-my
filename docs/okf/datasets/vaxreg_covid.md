---
type: "Dataset"
title: "Daily COVID-19 Vaccine Registrations by State"
description: "DataPulse projection of Daily COVID-19 Vaccine Registrations by State from Ministry of Health Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=vaxreg_covid"
tags: ["data.gov.my (OpenAPI)","non-vertical","daily"]
sources:
  - {"id": "kkm","resource": "https://api.data.gov.my/data-catalogue?id=vaxreg_covid","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Ministry of Health Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/vaxreg_covid.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 6205
stale_after: "2022-02-23T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Daily COVID-19 Vaccine Registrations by State is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `3`
- `first_row_hash`: `shape-v1:65ee238e27291a95e8ee3450c52b96bf993be2a4b08fe17e2752db9a0511ea83`
- `record_count`: `6205`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/vaxreg_covid.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
