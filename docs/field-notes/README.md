---
title: DataPulse MY — Field Notes
date: 2026-08-09
type: index
---

# DataPulse MY — Field Notes

Field notes are dated observations from probing Malaysian public data,
written as discoveries happened. Each note links to the commits,
deploys, or session evidence that proves the observation was real at
that time.

This page is the index, written on 2026-08-09. The notes themselves
are not backdated — each carries the date the work was actually done.

## The notes

| # | Date | Title | Evidence |
|---|---|---|---|
| [1](2026-07-31-initial-scaffold-and-first-datasets.md) | 2026-07-31 | Initial scaffold + the first two datasets (fuelprice, eperolehan) | commit `f941432`, `62b8413`, `a9e7a7f`, `ca4630e` |
| [2](2026-08-01-bnm-exchange-rate-cadence-discovered.md) | 2026-08-01 | BNM exchange rates — discovering the 4×/day cadence | commits `f99c06f`–`e928648` |
| [3](2026-08-02-fuelprice-schema-correction.md) | 2026-08-02 | T32 fuelprice schema-correction bug | commit `d075009` |
| [4](2026-08-05-audit-findings.md) | 2026-08-05 | Audit: 9 documentation gaps we didn't know we had | `docs/AUDIT-2026-08-05.md` |
| [5](2026-08-07-competitive-audit.md) | 2026-08-07 | Competitive audit: the MY open-data wrapper space is crowded | `references/competitive-audit-2026-08-07.md` |
| [6](2026-08-07-trust-layer-moat.md) | 2026-08-07 | Trust-layer audit: continuous verified health is unclaimed | `references/trust-layer-competitor-audit-2026-08-07.md` |
| [7](2026-08-09-moat-widening.md) | 2026-08-09 | Moat widening: 122 → 335 datasets, all verified (archived) | commits `3112e9d` etc. |
| [8](2026-08-09-uf-fix.md) | 2026-08-09 | CVE-class bug: 155 unknown-freshness (T32 at 10× scale) | commits `7563634`, `f49d72e` |
| [9](2026-08-09-odin-number-one.md) | 2026-08-09 | ODIN #1: the availability-vs-verification gap | World Bank + Bernama + DOSM |

## Why field notes

Three reasons:

1. **Evidence of work** — the dates + commit hashes prove when the discoveries happened. Anyone can audit the trail.
2. **Methodology capture** — each fix becomes a piece of intellectual property competitors can't retroactively accumulate.
3. **Citable artifacts** — analysts, journalists, and procurement teams can link to specific field notes. That's free distribution.

## How they're written

- **Honest dates** — each note carries the date the work was done, not when it was written.
- **Short** — 300–500 words each. Specific, evidence-based, no marketing.
- **Linked to evidence** — every claim links to a commit, a deploy run, a session log, or a primary source.
- **Dated revision** — when a note is updated, the change is appended, not erased.

## Why no backdating

We started this project on 2026-07-31. The notes on this page are
indexed by the date the discoveries actually happened. Some of the
later notes (8, 9) were written today but describe work done over the
past 10 days; the dates reflect when the discoveries happened, not
when the prose was typed.

A backdated field note is just marketing copy. An honestly-dated field
note is proof of work.
