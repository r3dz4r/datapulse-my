---
id: "npra_drug_registration_guidance"
title: "NPRA Drug Registration Guidance Documents"
source_url: "https://www.npra.gov.my/index.php/en/drug-registration-guidance-documents-drgd-e-book.html"
source_name: "National Pharmaceutical Regulatory Agency"
licence: "Reuse terms not stated on source page"
refresh_frequency: "weekly"
last_checked: 2026-08-08T06:00:59Z
last_observed: null
last_modified: null
record_count: 38
column_count: null
status: unknown-freshness
notes: "Document-set manifest. Discover the complete DRGD, main body, update lists, and appendix links from the landing page on every probe; require at least 12 distinct appendix-labelled resources rather than hardcoding revision-specific filenames."
dataset_id: npra_drug_registration_guidance
freshness_delta: unknown
next_expected_update: "weekly"
schema_version: 1.0
schema_drift: none
known_quirks:
  - "The landing page has no Last-Modified header, so HTTP 200 alone remains unknown-freshness"
  - "Appendix labels include lettered supplements, so the discovered link count can exceed the highest numbered appendix"
  - "Revision names and PDF paths change; consumers must discover links from the landing page"
breaking_changes: []
attribution: "National Pharmaceutical Regulatory Agency, Ministry of Health Malaysia"
---

# NPRA Drug Registration Guidance Documents

## Status

**Status:** Unknown-freshness

**Freshness:** Unknown

HTTP 200

## Provenance

NPRA publishes the Drug Registration Guidance Document (DRGD), its main body,
the complete compilation, update lists, and individual appendices from:

- `https://www.npra.gov.my/index.php/en/drug-registration-guidance-documents-drgd-e-book.html`

The landing page was reachable during the recorded check and exposed 38
distinct appendix-labelled links, including lettered supplements. The probe
discovers the current set weekly and uses 12 as the minimum structural floor;
it does not pin revision-specific PDF filenames.

## Schema

Each discovered resource should retain: document label, title, resolved URL,
document role (complete, main body, update list, or appendix), appendix number
or supplement label when present, and the revision/date text published by NPRA.

## Freshness semantics

The source returns HTTP 200 but no `Last-Modified` header. Under DataPulse MY's
existing eight-status taxonomy, reachability without defensible freshness
evidence is `unknown-freshness`. A missing landing page is `unreachable`; a
reachable page with fewer than the minimum appendix resources is `degraded`.

## Reproducibility

```sh
curl -sS -I \
  "https://www.npra.gov.my/index.php/en/drug-registration-guidance-documents-drgd-e-book.html"
curl -sS \
  "https://www.npra.gov.my/index.php/en/drug-registration-guidance-documents-drgd-e-book.html" \
  | grep -oE '>Appendix [0-9]+[A-Z]?<' | sort -u
```

## Licence

The source page does not state reuse terms for the DRGD document set. Preserve
NPRA attribution and verify downstream redistribution rights before packaging
the documents in a paid product.
