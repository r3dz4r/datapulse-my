---
type: "Dataset"
title: "OpenDOSM Annual Nominal GDP and GNI"
description: "DataPulse projection of OpenDOSM Annual Nominal GDP and GNI from DOSM Malaysia."
resource: "https://storage.dosm.gov.my/gdp/gdp_gni_annual_nominal.csv"
tags: ["OpenDOSM (storage.dosm.gov.my)","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://storage.dosm.gov.my/gdp/gdp_gni_annual_nominal.csv","title": "DOSM Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-04T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "DOSM via OpenDOSM"
datapulse:real_status: "aging"
datapulse:health_report: "/data/dosm_gdp_gni_annual_nominal.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: null
stale_after: "2026-07-02T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

OpenDOSM Annual Nominal GDP and GNI is published by DOSM Malaysia and tracked by DataPulse. The latest published probe classifies it as `aging`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:4174cbaabb1b0960337c3a7a2b39de1cdf508affed5684b4dc10bf146d25053d`
- `record_count`: `157`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_gdp_gni_annual_nominal.md). The probe is described by [the opendosm_storage attested computation](/computations/opendosm-storage.md).
