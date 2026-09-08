---
type: "Dataset"
title: "Number of Registered .MY Domains with DNSSEC"
description: "DataPulse projection of Number of Registered .MY Domains with DNSSEC from MYNIC and Ministry of Digital."
resource: "https://api.data.gov.my/data-catalogue?id=domains_dnssec"
tags: ["data.gov.my (OpenAPI)","non-vertical","monthly"]
sources:
  - {"id": "mynic","resource": "https://api.data.gov.my/data-catalogue?id=domains_dnssec","title": "MYNIC and Ministry of Digital"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "MYNIC and Ministry of Digital via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/domains_dnssec.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 3663
stale_after: "2025-02-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Number of Registered .MY Domains with DNSSEC is published by MYNIC and Ministry of Digital and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:895d4e9d85ed0dae4eb8c31373fb4fd3ab5693e529a8f1ce181bf70d579e8f7b`
- `record_count`: `3663`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/domains_dnssec.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
