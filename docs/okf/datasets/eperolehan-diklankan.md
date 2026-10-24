---
type: "Dataset"
title: "ePerolehan Tender Notices (DIIKLANKAN)"
description: "DataPulse projection of ePerolehan Tender Notices (DIIKLANKAN) from Ministry of Finance Malaysia."
resource: "https://www.eperolehan.gov.my/quotation-tender-notice"
tags: ["ePerolehan","non-vertical","hourly"]
sources:
  - {"id": "mof","resource": "https://www.eperolehan.gov.my/quotation-tender-notice","title": "Ministry of Finance Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-10-23T14:07:07Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "MOF ePerolehan"
datapulse:real_status: "unreachable"
datapulse:health_report: "/data/eperolehan-diklankan.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
---

# Summary

ePerolehan Tender Notices (DIIKLANKAN) is published by Ministry of Finance Malaysia and tracked by DataPulse. The latest published probe classifies it as `unreachable`.

# Schema

No structural fingerprint was recorded by the latest probe.

# Quirks

URL responds but row extraction produced no result (body may be binary/JSON/empty)

# Health

See the [published health report](/data/eperolehan-diklankan.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
