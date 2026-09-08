---
type: "Dataset"
title: "Interest Volume: Banking Institutions"
description: "DataPulse projection of Interest Volume: Banking Institutions from Bank Negara Malaysia."
resource: "https://api.bnm.gov.my/public/interest-volume"
tags: ["BNM Open API (apikijangportal.bnm.gov.my)","non-vertical","monthly"]
sources:
  - {"id": "bnm","resource": "https://api.bnm.gov.my/public/interest-volume","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via BNM Open API"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/bnm_interest_volume.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 3
stale_after: "2026-10-20T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Interest Volume: Banking Institutions is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `column_count`: `9`
- `first_row_hash`: `shape-v1:3a96e911e43192d8fcb6ece4b72e377ef579d2eebdec507eaf7155fd9e3ee7b7`
- `record_count`: `3`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_interest_volume.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
