---
type: "Dataset"
title: "COVID-19 Deaths Line List"
description: "DataPulse projection of COVID-19 Deaths Line List from Ministry of Health Malaysia."
resource: "https://storage.data.gov.my/healthcare/covid_deaths_linelist.csv"
tags: ["data.gov.my","non-vertical","annual"]
sources:
  - {"id": "kkm","resource": "https://storage.data.gov.my/healthcare/covid_deaths_linelist.csv","title": "Ministry of Health Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-08T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Ministry of Health Malaysia via data.gov.my"
datapulse:real_status: "aging"
datapulse:health_report: "/data/covid_deaths_linelist.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 37351
stale_after: "2025-11-16T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

COVID-19 Deaths Line List is published by Ministry of Health Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `15`
- `first_row_hash`: `shape-v1:988672890b11f504f7506db9d377cd6e74131398964cff972692e8f78242b0fd`
- `record_count`: `37351`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/covid_deaths_linelist.md). The probe is described by [the data_gov_my attested computation](/computations/data-gov-my.md).
