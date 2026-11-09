---
type: "Dataset"
title: "ODIN Country Reference"
description: "DataPulse projection of ODIN Country Reference from Open Data Watch."
resource: "https://odin-aim.akroninc.net/api/api/client/GetCountries"
tags: ["Open Data Watch -- Open Data Inventory","non-vertical","as-required"]
sources:
  - {"id": "odin","resource": "https://odin-aim.akroninc.net/api/api/client/GetCountries","title": "Open Data Watch"}
generated: {"by": "process:datapulse-pipeline","at": "2026-10-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-11-08T16:36:56Z"}
status: "stable"
datapulse:licence: "CC-BY-4.0"
datapulse:attribution: "Open Data Watch -- Open Data Inventory (ODIN), https://odin.opendatawatch.com. Licensed under CC BY 4.0."
datapulse:real_status: "reference"
datapulse:health_report: "/data/odin_countries.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 243
---

# Summary

ODIN Country Reference is published by Open Data Watch and tracked by DataPulse. The latest published probe classifies it as `reference`.

# Schema

- `column_count`: `15`
- `first_row_hash`: `shape-v1:01c781ac072d23c7aeeaed07a6d919155bb1ffe97b4d7eb5e7773b352db8fc88`
- `record_count`: `243`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/odin_countries.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
