---
title: T32 fuelprice schema-correction bug
date: 2026-08-02
status: final
evidence:
  - commit: d075009
    description: Correct fuelprice schema — real fields are ron95/ron97/diesel + subsidy variants (was incorrectly documented as petrol_ron95 etc.)
---

# Field Note 3 — T32 fuelprice schema-correction bug

**Date:** 2026-08-02
**Author:** Redza Halim (with operator)
**Subject:** The first parser-fix precedent: the fuelprice schema was wrong

## What happened

When we first added the fuelprice dataset (commit `a9e7a7f`,
2026-07-31), we documented the columns based on the data.gov.my
catalogue page. The catalogue said columns were `petrol_ron95`,
`petrol_ron97`, `diesel`. We wrote the health report and JSON
envelope to match.

Today we actually fetched a recent CSV and discovered the real
columns are `ron95`, `ron97`, `diesel`, plus subsidy variants. The
catalogue page had a different (and outdated) schema. Anyone using
our JSON envelope to fetch fuel prices would have gotten NULL for
every value.

This is the same failure class as the much larger 155-dataset
unknown-freshness bug we hit on 2026-08-09 — both are
**"the metadata doesn't match the content"** failures. The 2026-08-09
case was much larger because it covered every dgm_/dosm_ dataset
that didn't have a `content-date-field` in probe-policy.json; this
2026-08-02 case was the precedent that taught us to check.

## What we learned

1. **Catalogue metadata is not the source of truth.** The
   `data.gov.my` catalogue page is human-curated and lags the actual
   data. For trust layers, **the probe is the source of truth** —
   it fetches the data, parses it, and reports the actual schema.
   The catalogue is a hint, not a contract.

2. **First-day schema mistakes are inevitable.** Within 24 hours of
   documenting fuelprice, we were wrong. That's normal. The fix is
   a discipline: every dataset gets re-verified within the first
   week, and any field mismatch goes into a `schema_drift` field on
   the per-dataset report.

3. **T32 is the naming.** We named this class of bug T32 — parser-fix
   precedents. Future T-class bugs reference T32 as the canonical
   example.

## How we fixed it

Commit `d075009` updated:
- `data/fuelprice.md` — corrected column names
- `data/json/fuelprice.json` — corrected envelope schema
- `scripts/probe-policy.json` — added fuelprice to the explicit
  freshness entries

## Files

- `data/fuelprice.md` — corrected
- `data/json/fuelprice.json` — corrected

## Notes for the field

This is the canonical T-class bug for trust layers. Every project
that scrapes government open data will hit it. The lesson is: **the
first report you write for a dataset is a hypothesis, not a fact**.
Treat it as a draft, re-verify within 7 days, and document any
corrections. The corrections ARE the value — they're proof that the
trust layer actually probes, not just catalogues.
