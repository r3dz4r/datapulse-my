---
type: "Dataset"
title: "ODIN Region Reference"
description: "DataPulse projection of ODIN Region Reference from Open Data Watch."
resource: "https://odin-aim.akroninc.net/api/api/client/GetRegions"
tags: ["Open Data Watch -- Open Data Inventory","non-vertical","as-required"]
sources:
  - {"id": "odin","resource": "https://odin-aim.akroninc.net/api/api/client/GetRegions","title": "Open Data Watch"}
generated: {"by": "process:datapulse-pipeline","at": "2026-10-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-11-08T16:36:56Z"}
status: "stable"
datapulse:licence: "CC-BY-4.0"
datapulse:attribution: "Open Data Watch -- Open Data Inventory (ODIN), https://odin.opendatawatch.com. Licensed under CC BY 4.0."
datapulse:real_status: "reference"
datapulse:health_report: "/data/odin_regions.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 21
---

# Summary

ODIN Region Reference is published by Open Data Watch and tracked by DataPulse. The latest published probe classifies it as `reference`.

# Schema

- `column_count`: `7`
- `first_row_hash`: `shape-v1:19d51b237200ebba425e5fb668fc8a273f96720595b7fc5930656f779d1df6eb`
- `record_count`: `21`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/odin_regions.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
