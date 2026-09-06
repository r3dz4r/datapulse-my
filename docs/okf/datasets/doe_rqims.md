---
type: "Dataset"
title: "DOE RQIMS River Water Quality (Continuous)"
description: "DataPulse projection of DOE RQIMS River Water Quality (Continuous) from Department of Environment Malaysia."
resource: "https://eqms.doe.gov.my/RQIMS/conti_river"
tags: ["DOE MyEQMS portal (Camofox-rendered)","non-vertical","hourly"]
sources:
  - {"id": "doe","resource": "https://eqms.doe.gov.my/RQIMS/conti_river","title": "Department of Environment Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T17:16:08Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "DOE Malaysia via MyEQMS"
datapulse:real_status: "browser-dependent"
datapulse:health_report: "/data/doe_rqims.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-09-07T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

DOE RQIMS River Water Quality (Continuous) is published by Department of Environment Malaysia and tracked by DataPulse. The latest published probe classifies it as `browser-dependent`.

# Schema

No structural fingerprint was recorded by the latest probe.

# Quirks

URL responds but row extraction produced no result (body may be binary/JSON/empty)

# Health

See the [published health report](/data/doe_rqims.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
