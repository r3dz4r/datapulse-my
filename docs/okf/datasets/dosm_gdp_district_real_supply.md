---
type: "Dataset"
title: "Annual Real GDP by District & Economic Sector"
description: "DataPulse projection of Annual Real GDP by District & Economic Sector from Department of Statistics Malaysia."
resource: "https://api.data.gov.my/data-catalogue?id=gdp_district_real_supply"
tags: ["DOSM via data.gov.my","non-vertical","annual"]
sources:
  - {"id": "dosm","resource": "https://api.data.gov.my/data-catalogue?id=gdp_district_real_supply","title": "Department of Statistics Malaysia"}
generated: {"by": "process:datapulse-pipeline","at": "2026-08-09T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-05T02:34:56Z"}
status: "stable"
datapulse:licence: "Creative Commons Attribution 4.0"
datapulse:attribution: "Department of Statistics Malaysia via data.gov.my"
datapulse:real_status: "stale"
datapulse:health_report: "/data/dosm_gdp_district_real_supply.md"
datapulse:methodology_version: 2
datapulse:expected_record_count: 10000
stale_after: "2021-07-01T12:00:00Z"
datapulse:stale_after_basis: "cadence"
---

# Summary

Annual Real GDP by District & Economic Sector is published by Department of Statistics Malaysia and tracked by DataPulse. The latest published probe classifies it as `stale`.

# Schema

- `column_count`: `6`
- `first_row_hash`: `shape-v1:7aee0bb274c2dfac3d3e342ed8799c72a8e2ca7e6b07fe6175f1606a63f4b488`
- `record_count`: `10626`

# Quirks

No probe quirks were recorded.

# Health

See the [published health report](/data/dosm_gdp_district_real_supply.md). The probe is described by [the dosm_via_data_gov_my attested computation](/computations/dosm-via-data-gov-my.md).
