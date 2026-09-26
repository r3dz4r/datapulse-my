---
type: "Dataset"
title: "HDB Resale Flat Prices Jan-2017 onwards (SG)"
description: "DataPulse projection of HDB Resale Flat Prices Jan-2017 onwards (SG) from Singapore Government."
resource: "https://api-production.data.gov.sg/v2/public/api/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/list-rows"
tags: ["data.gov.sg","non-vertical","monthly"]
sources:
  - {"id": "sg-datagov","resource": "https://api-production.data.gov.sg/v2/public/api/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/list-rows","title": "Singapore Government"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-07T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-20T20:40:30Z"}
status: "stable"
datapulse:licence: "Singapore Open Data Licence v1.0 (attribution required)"
datapulse:attribution: "Contains information from Housing & Development Board, Singapore Open Data Licence v1.0"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/sg_datagov_hdb_resale_prices.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-11-06T06:10:23Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

HDB Resale Flat Prices Jan-2017 onwards (SG) is published by Singapore Government and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `first_row_hash`: `shape-v1:72c0c72b54099477d5780569400aa571dbbc335c19010222856c530b12c17404`
- `record_count`: `3`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/sg_datagov_hdb_resale_prices.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
