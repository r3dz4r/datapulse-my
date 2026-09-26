---
type: "Dataset"
title: "Overnight Policy Rate (OPR)"
description: "DataPulse projection of Overnight Policy Rate (OPR) from Bank Negara Malaysia."
resource: "https://api.bnm.gov.my/public/opr"
tags: ["BNM Open API (apikijangportal.bnm.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://api.bnm.gov.my/public/opr","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-26T02:49:53Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via BNM Open API"
datapulse:real_status: "reference"
datapulse:health_report: "/data/bnm_opr.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 1
---

# Summary

Overnight Policy Rate (OPR) is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `reference`.

# Schema

- `first_row_hash`: `shape-v1:112e3d921f8c2b5d106f2546c1a5b1201a9d99012f4823c200f7cd855d03d6cf`
- `record_count`: `2`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_opr.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
