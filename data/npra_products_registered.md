---
id: "npra_products_registered"
title: "Verified Malaysian Pharmaceutical Registry"
source_url: "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv"
source_name: "NPRA via data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "daily"
last_checked: 2026-08-08T06:00:59Z
last_observed: null
last_modified: 2026-08-06T22:31:03Z
record_count: 28024
column_count: 16
status: fresh
notes: "Paid-product raw manifest. The probe accepts legacy compact MAL registration values and the MAL + 8-digit Registration Number + Product Classification representation introduced on 2026-08-10; incompatible rows use the existing degraded status. Source age continues through the existing fresh/aging/stale taxonomy."
dataset_id: npra_products_registered
freshness_delta: 1 days
next_expected_update: "daily"
schema_version: 1.0
schema_drift: none
known_quirks:
  - "QUEST3+ returns HTTP 400 to curl's default user agent; a browser-like user agent returns HTTP 200"
  - "date_reg and date_end may contain future administrative dates and are not reliable publication-freshness signals"
  - "registration values are case-normalised before old/new transition-format validation"
breaking_changes:
  - "From 2026-08-10, accept MAL + 8-digit Registration Number + Product Classification while retaining legacy-format support during the transition window"
attribution: "National Pharmaceutical Regulatory Agency, Ministry of Health Malaysia via data.gov.my"
---

# Verified Malaysian Pharmaceutical Registry

## Status

**Status:** Fresh

**Freshness:** 1 days

HTTP 200

## Provenance

NPRA exposes its public registered/notified-product search through the consumer
page and its embedded QUEST3+ application:

- `https://www.npra.gov.my/index.php/my/consumers-2/maklumat/carian-produk-berdaftar-bernotifikasi.html`
- `https://quest3plus.bpfk.gov.my/pmo2/index.php`

The agent-ready full-registry payload is the official data.gov.my mirror:

- `https://storage.data.gov.my/healthcare/pharmaceutical_products.csv`

The consumer page, QUEST3+ application, and CSV mirror were reachable during
the recorded check. The search application supports product name, registration
number, holder, manufacturer, and importer searches.

## Schema

The verified CSV contains 16 columns: `reg_no`, `ref_no`, `product`, `status`,
`description`, `holder`, `holder_osa`, `manufacturer`, `manufacturer_osa`,
`importer`, `importer_osa`, `date_reg`, `date_end`, `active_ingredient`,
`mdc_code`, and `generic_name`.

## Registration-number transition

NPRA's 2026-08-10 format transition is treated as a compatibility window. The
probe accepts both compact legacy values such as `MAL19913374AZ` and the new
`MAL + 8-digit Registration Number + Product Classification` representation.
It case-normalises the source value and tolerates transition separators without
discarding the product-classification suffix. A row outside both accepted
forms makes the probe `degraded`; it does not create a new health status.

## Freshness semantics

The daily check uses the source `Last-Modified` header. Future administrative
dates in `date_reg` or `date_end` are rejected as freshness evidence. Records
older than the configured cadence move through the existing `aging` and
`stale` statuses.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv"
curl -sS "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv" | head -1
curl -sS -A "Mozilla/5.0" \
  "https://quest3plus.bpfk.gov.my/pmo2/index.php" | head -50
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: National
Pharmaceutical Regulatory Agency, Ministry of Health Malaysia via data.gov.my.
