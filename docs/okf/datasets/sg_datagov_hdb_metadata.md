---
type: "Dataset"
title: "HDB Dataset Metadata (SG)"
description: "DataPulse projection of HDB Dataset Metadata (SG) from Singapore Government."
resource: "https://api-production.data.gov.sg/v2/public/api/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/metadata"
tags: ["data.gov.sg","non-vertical","monthly"]
sources:
  - {"id": "sg-datagov","resource": "https://api-production.data.gov.sg/v2/public/api/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/metadata","title": "Singapore Government"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-07T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-20T20:40:30Z"}
status: "stable"
datapulse:licence: "Singapore Open Data Licence v1.0 (attribution required)"
datapulse:attribution: "Contains information from Housing & Development Board, Singapore Open Data Licence v1.0"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/sg_datagov_hdb_metadata.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-11-06T06:10:23Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

HDB Dataset Metadata (SG) is published by Singapore Government and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `first_row_hash`: `shape-v1:d9cce02b9a0da71779a2107c8b573297d84e5ee200728574636f47c85cc82c53`
- `record_count`: `3`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/sg_datagov_hdb_metadata.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
