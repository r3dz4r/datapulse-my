---
type: "Dataset"
title: "KKM iDengue Weekly Dengue Cases"
description: "DataPulse projection of KKM iDengue Weekly Dengue Cases from KKM (Bahagian Kawalan Penyakit) + MYSA."
resource: "https://idengue.mysa.gov.my/"
tags: ["KKM iDengue portal (Camofox-rendered)","non-vertical","daily"]
sources:
  - {"id": "kkm","resource": "https://idengue.mysa.gov.my/","title": "KKM (Bahagian Kawalan Penyakit) + MYSA"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-07T05:30:21Z"}
status: "stable"
datapulse:licence: "Open Government Licence (Malaysia)"
datapulse:attribution: "KKM via iDengue portal (MYSA hosted)"
datapulse:real_status: "browser-dependent"
datapulse:health_report: "/data/kkm_idengue.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
---

# Summary

KKM iDengue Weekly Dengue Cases is published by KKM (Bahagian Kawalan Penyakit) + MYSA and tracked by DataPulse. The latest published probe classifies it as `browser-dependent`.

# Schema

No structural fingerprint was recorded by the latest probe.

# Quirks

URL responds but row extraction produced no result (body may be binary/JSON/empty)

# Health

See the [published health report](/data/kkm_idengue.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
