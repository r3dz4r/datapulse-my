---
type: "Dataset"
title: "Number of Active Government Mobile Applications"
description: "DataPulse projection of Number of Active Government Mobile Applications from National Digital Department and Ministry of Digital."
resource: "https://api.data.gov.my/data-catalogue?id=government_apps_active"
tags: ["data.gov.my (OpenAPI)","non-vertical","monthly"]
sources:
  - {"id": "jdn","resource": "https://api.data.gov.my/data-catalogue?id=government_apps_active","title": "National Digital Department and Ministry of Digital"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "National Digital Department and Ministry of Digital via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/government_apps_active.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 137
stale_after: "2026-05-17T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Number of Active Government Mobile Applications is published by National Digital Department and Ministry of Digital and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:880181f291857c8955da6d56c35fe5c764944cfa1826d77ef7becde61d00ef75`
- `record_count`: `137`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/government_apps_active.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
