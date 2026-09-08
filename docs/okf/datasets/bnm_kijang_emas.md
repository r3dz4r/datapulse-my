---
type: "Dataset"
title: "Kijang Emas (Gold Reference Price)"
description: "DataPulse projection of Kijang Emas (Gold Reference Price) from Bank Negara Malaysia."
resource: "https://api.bnm.gov.my/public/kijang-emas"
tags: ["BNM Open API (apikijangportal.bnm.gov.my)","non-vertical","daily"]
sources:
  - {"id": "bnm","resource": "https://api.bnm.gov.my/public/kijang-emas","title": "Bank Negara Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-10T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Bank Negara Malaysia via BNM Open API"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/bnm_kijang_emas.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: 2
stale_after: "2026-09-08T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Kijang Emas (Gold Reference Price) is published by Bank Negara Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `record_count`: `2`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/bnm_kijang_emas.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
