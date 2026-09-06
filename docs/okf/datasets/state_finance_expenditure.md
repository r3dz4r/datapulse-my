---
type: "Dataset"
title: "State Government Expenditure"
description: "DataPulse projection of State Government Expenditure from National Audit Department Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=state_finance_expenditure"
tags: ["data.gov.my (OpenAPI)","non-vertical","annual"]
sources:
  - {"id": "national_audit","resource": "https://api.data.gov.my/data-catalogue?id=state_finance_expenditure","title": "National Audit Department Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "National Audit Department Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/state_finance_expenditure.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 104
stale_after: "2023-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

State Government Expenditure is published by National Audit Department Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:6edee2599e800d854bf33b26e58381434e7cd86e27f907efe0e1c201e5f168a0`
- `record_count`: `104`

# Quirks

publisher-likely-retired

# Health

See the [published health report](/data/state_finance_expenditure.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
