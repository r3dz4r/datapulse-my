---
type: "Dataset"
title: "School Completion Rates by State"
description: "DataPulse projection of School Completion Rates by State from Ministry of Education Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=completion_school_state"
tags: ["data.gov.my (OpenAPI)","non-vertical","annual"]
sources:
  - {"id": "moe","resource": "https://api.data.gov.my/data-catalogue?id=completion_school_state","title": "Ministry of Education Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-11-05T03:33:57Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Ministry of Education"
datapulse:real_status: "aging"
datapulse:health_report: "/data/completion_school_state.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 1071
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

School Completion Rates by State is published by Ministry of Education Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `5`
- `first_row_hash`: `shape-v1:53f8dafa1045290d2858227b3655bb7c4f44d31f81ff87e654536f359f876efa`
- `record_count`: `1530`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/completion_school_state.md). The probe is described by [the data_gov_my_openapi attested computation](/computations/data-gov-my-openapi.md).
