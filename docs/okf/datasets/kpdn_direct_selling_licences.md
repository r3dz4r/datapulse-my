---
type: "Dataset"
title: "KPDN Direct Selling AJL Licence Register (Act 500)"
description: "DataPulse projection of KPDN Direct Selling AJL Licence Register (Act 500) from Kementerian Perdagangan Dalam Negeri dan Kos Sara Hidup (KPDN)."
resource: "https://www.kpdn.gov.my/perkhidmatan-kpdn/jom-berniaga/pembangunan-industri-jualan-langsung/status-syarikat-jualan-langsung"
tags: ["KPDN","non-vertical","daily"]
sources:
  - {"id": "kpdn","resource": "https://www.kpdn.gov.my/perkhidmatan-kpdn/jom-berniaga/pembangunan-industri-jualan-langsung/status-syarikat-jualan-langsung","title": "Kementerian Perdagangan Dalam Negeri dan Kos Sara Hidup (KPDN)"}
generated: {"by": "process:datapulse-pipeline","at": "2026-11-12T00:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-11-12T13:21:29Z"}
status: "stable"
datapulse:licence: "Reuse licence not stated on the KPDN source pages; permission unverified"
datapulse:attribution: "Kementerian Perdagangan Dalam Negeri dan Kos Sara Hidup (KPDN)"
datapulse:real_status: "unknown-freshness"
datapulse:health_report: "/data/kpdn_direct_selling_licences.md"
datapulse:methodology_version: 3
datapulse:expected_record_count: null
---

# Summary

KPDN Direct Selling AJL Licence Register (Act 500) is published by Kementerian Perdagangan Dalam Negeri dan Kos Sara Hidup (KPDN) and tracked by DataPulse. The latest published probe classifies it as `unknown-freshness`.

# Schema

- `record_count`: `1856`

# Quirks

Primary HTTP probe checks reachability only. The scoped observation generator reads both Malay source pages, including the main register's cancellation tab. Licence dates are not publication dates; reuse terms, sector and operations address are not stated.

# Health

See the [published health report](/data/kpdn_direct_selling_licences.md). The probe is described by [the unclassified attested computation](/computations/unclassified.md).
