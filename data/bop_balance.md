---
id: "bop_balance"
title: "Balance of Payments by Account"
source_url: "https://storage.dosm.gov.my/bop/bop_balance.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "quarterly"
last_checked: 2026-08-11T14:21:08Z
last_observed: 2026-01-01
last_modified: 2026-05-15T04:45:33Z
record_count: 325
column_count: 3
status: aging
notes: "Tier-1 wave A already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: bop_balance
freshness_delta: 222 days
next_expected_update: "quarterly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Balance of Payments by Account

## Status

**Status:** Aging

**Freshness:** 222 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 9,639 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/bop/bop_balance.csv`

## Coverage

Malaysia. Latest source observation: 2026-01-01.

## Schema

The verified CSV contains 3 columns: `date`, `account`, `balance`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/bop/bop_balance.csv"
curl -sS "https://storage.dosm.gov.my/bop/bop_balance.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
