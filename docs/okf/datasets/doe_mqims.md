---
type: "Dataset"
title: "DOE MQIMS Marine Water Quality (Manual)"
description: "DataPulse projection of DOE MQIMS Marine Water Quality (Manual) from Department of Environment Malaysia."
resource: "https://eqms.doe.gov.my/MQIMS/main"
tags: ["DOE MyEQMS portal (Camofox-rendered)","non-vertical","monthly"]
sources:
  - {"id": "doe","resource": "https://eqms.doe.gov.my/MQIMS/main","title": "Department of Environment Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-10-10T11:37:57Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "Data and information are subject to the Malaysian Government Open Data Terms of Use 1.0"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/doe_mqims.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
stale_after: "2026-11-25T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

DOE MQIMS Marine Water Quality (Manual) is published by Department of Environment Malaysia and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

No structural fingerprint was recorded by the latest probe.

# Quirks

URL responds but row extraction produced no result (body may be binary/JSON/empty)

# Health

See the [published health report](/data/doe_mqims.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
