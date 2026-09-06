---
type: "Dataset"
title: "MBPP Weather Station Observations"
description: "DataPulse projection of MBPP Weather Station Observations from Majlis Bandaraya Pulau Pinang (MBPP)."
resource: "https://vip.mbpp.gov.my/vipserver/rest/services/Weather_Station/FeatureServer/50"
tags: ["MBPP ArcGIS FeatureServer","non-vertical","hourly"]
sources:
  - {"id": "mbpp","resource": "https://vip.mbpp.gov.my/vipserver/rest/services/Weather_Station/FeatureServer/50","title": "Majlis Bandaraya Pulau Pinang (MBPP)"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-06T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T17:16:08Z"}
status: "stable"
datapulse:licence: "MBPP Government Open Data Terms (attribution required)"
datapulse:attribution: "Majlis Bandaraya Pulau Pinang (MBPP), Government Open Data Terms: https://www.mbpp.gov.my/en/terma-penggunaan-data-terbuka"
datapulse:real_status: "fresh"
datapulse:health_report: "/data/mbpp_weather_stations.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 28
stale_after: "2026-09-08T05:13:26Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

MBPP Weather Station Observations is published by Majlis Bandaraya Pulau Pinang (MBPP) and tracked by DataPulse. The latest published probe classifies it as `fresh`.

# Schema

- `schema_fingerprint`: `sha256:96cab38cc1da00b6df4296ff1f70e0666367c82c3069e615b65b8b9137bd7cb1`
- `column_count`: `50`
- `record_count`: `28`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/mbpp_weather_stations.md). The probe is described by [the mbpp_arcgis_observation attested computation](/computations/mbpp-arcgis-observation.md).
