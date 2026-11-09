---
type: "Dataset"
title: "ODIN Income Group Reference"
description: "DataPulse projection of ODIN Income Group Reference from Open Data Watch."
resource: "https://odin-aim.akroninc.net/api/api/client/GetIncomeGroups"
tags: ["Open Data Watch -- Open Data Inventory","non-vertical","as-required"]
sources:
  - {"id": "odin","resource": "https://odin-aim.akroninc.net/api/api/client/GetIncomeGroups","title": "Open Data Watch"}
generated: {"by": "process:datapulse-pipeline","at": "2026-10-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-11-08T16:36:56Z"}
status: "stable"
datapulse:licence: "CC-BY-4.0"
datapulse:attribution: "Open Data Watch -- Open Data Inventory (ODIN), https://odin.opendatawatch.com. Licensed under CC BY 4.0."
datapulse:real_status: "reference"
datapulse:health_report: "/data/odin_income_groups.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 5
---

# Summary

ODIN Income Group Reference is published by Open Data Watch and tracked by DataPulse. The latest published probe classifies it as `reference`.

# Schema

- `column_count`: `4`
- `first_row_hash`: `shape-v1:4ef75839b2ab5ab2d7a0b73f8dbae035a99689abcf74a823e65be2b38e2661bc`
- `record_count`: `5`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/odin_income_groups.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
