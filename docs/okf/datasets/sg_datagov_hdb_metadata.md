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
  - {"by": "process:datapulse-health-timer","at": "2026-11-26T04:55:46Z"}
status: "stable"
datapulse:licence: "Singapore Open Data Licence v1.0 (attribution required)"
datapulse:attribution: "Contains information from Housing & Development Board, Singapore Open Data Licence v1.0; accessed 2026-09-07"
datapulse:real_status: "degraded"
datapulse:health_report: "/data/sg_datagov_hdb_metadata.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2027-01-11T06:10:15Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

HDB Dataset Metadata (SG) is published by Singapore Government and tracked by DataPulse. The latest published probe classifies it as `degraded`.

# Schema

- `first_row_hash`: `shape-v1:68849cfe13f083e4e88984313a698486842e5b4d120dd0150017e543228381a4`
- `record_count`: `3`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/sg_datagov_hdb_metadata.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
