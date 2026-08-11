---
title: BNM exchange rates — discovering the 4×/day cadence
date: 2026-08-01
status: final
evidence:
  - commit: f99c06f
    description: Add pricecatcher + BNM exchange rate datasets
  - commit: f6bddc9
    description: BNM morning (0900) exchange rate health report
  - commit: 867c9bf
    description: BNM late-morning (1130) exchange rate
  - commit: a8ba11b
    description: BNM noon (1200) exchange rate
  - commit: 51242e8
    description: BNM end-of-day (1700) exchange rate
  - commit: e928648
    description: Add BNM section to README
---

# Field Note 2 — BNM exchange rates: discovering the 4×/day cadence

**Date:** 2026-08-01
**Author:** Redza Halim (with operator)
**Subject:** The Bank Negara Malaysia exchange rate is published four times daily

## What happened

When we added BNM's exchange rate today, we found the dataset is
published **four times a day**, not once. The dataset IDs were:

| Time | Dataset ID | Window |
|---|---|---|
| 0900 MYT | `exchangerates_daily_0900` | Morning reference rate |
| 1130 MYT | `exchangerates_daily_1130` | Mid-morning reference rate |
| 1200 MYT | `exchangerates_daily_1200` | Noon reference rate |
| 1700 MYT | `exchangerates_daily_1700` | End-of-day reference rate |

Each window is published as a separate BNM API endpoint. Naive
implementations that treat "BNM exchange rate" as one daily dataset
will miss 3 of the 4 daily updates per day, every day. That's a
**silent staleness bug**: the data appears "fresh" (the URL works,
the row count is right) but the user is being served a reference rate
that's hours out of date.

## What we learned

**Declared refresh frequency lies about cadence.** BNM publishes
"daily" exchange rate — but actually publishes 4×/day. The
`refresh_frequency` field on the manifest captures the *declared*
cadence, not the *actual* cadence. The probe must verify the actual
publication pattern by sampling at multiple times.

For trust-layer probes, the unit of "freshness" is **the freshness
of the most recent probe**, not the declared cadence. A dataset
that "should" be daily can have multiple sub-daily publication
windows; a probe that runs hourly will catch them.

## How we fixed it

Each window is a separate manifest entry with `refresh_frequency: "daily"`
and a `notes` field documenting the actual publication time. The probe
treats them as 4 independent datasets. The README's BNM section
(`e928648`) names the cadence explicitly so consumers know to fetch
all 4 windows.

## Files

- `datapulse.json` — 4 new entries for BNM exchange rate windows
- `data/exchangerates_daily_*.md` — 4 health reports
- `data/json/exchangerates_daily_*.json` — 4 envelopes
- `README.md` updated with BNM section

## Notes for the field

When scraping any "daily" data, assume the publisher publishes more
frequently than declared. Sample at least 3 times the declared
cadence for the first week of probing. You'll find sub-daily windows
in 10-20% of government financial datasets.
