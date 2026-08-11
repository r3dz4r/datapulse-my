---
title: Initial scaffold + the first two datasets (fuelprice, eperolehan)
date: 2026-07-31
status: final
evidence:
  - commit: f941432
    description: Initial commit
  - commit: 62b8413
    description: Add fuelprice and eperolehan-diklankan to manifest
  - commit: a9e7a7f
    description: fuelprice health report + JSON envelope
  - commit: ca4630e
    description: eperolehan-diklankan health report + JSON envelope
  - commit: 9055f18
    description: README with project explanation
---

# Field Note 1 — Initial scaffold + the first two datasets

**Date:** 2026-07-31
**Author:** Redza Halim (with operator)
**Subject:** First commit; choosing the first two datasets to track

## What happened

The project started today. Initial commit `f941432` established the
manifest format, the JSON envelope schema, and the per-dataset
directory structure (`data/<id>.md` report + `data/json/<id>.json`
envelope). Within the same day, two datasets were added:

1. **fuelprice** — daily fuel price data from Ministry of Finance
   (`data.gov.my`).
2. **eperolehan-diklankan** — government procurement announcements
   (browser-dependent portal; needed Camofox sidecar from day one).

For each, we wrote a per-dataset health report (`a9e7a7f`,
`ca4630e`) with: source URL, licence, declared refresh frequency,
expected record count, observed data shape, and known quirks.

## What we learned

The per-dataset-report pattern (`data/<id>.md`) is the foundation of
the trust layer. It is **not** auto-generated; it's a human-curated
artifact that captures what auto-probes can and cannot determine. The
combination of (machine probe) + (human note) is the unit of verified
trust.

The Camofox dependency was introduced on day one because
`eperolehan-diklankan` is JavaScript-rendered. Without a real browser,
the probe cannot reach the data. This shaped the entire infrastructure
design: probe + browser sidecar + per-dataset adapter config.

## Files

- `datapulse.json` — initial manifest with 2 entries
- `data/fuelprice.md`, `data/eperolehan-diklankan.md` — health reports
- `data/json/fuelprice.json`, `data/json/eperolehan-diklankan.json` — envelopes
- `README.md` (`9055f18`) — initial project explanation
- `CONTRIBUTING.md` (`e4c3920`) — adopt-a-dataset model

## Notes for the field

A trust layer for public data lives or dies on the first 5 datasets.
If you can't get two right, you have no credibility for the 200th.
We chose the two most-requested categories (fuel + procurement)
specifically because they had active user demand — verifiability
matters most where people will check.
