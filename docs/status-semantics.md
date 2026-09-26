---
audience: agent and application builder, analyst, auditor
canonical: true
volatility: contract
owner: operator
review_trigger: when a status is added, renamed, or its evidence basis changes
last_verified: 2026-09-26
---

# Status semantics

This page is the compact consumer contract for the current DataPulse health vocabulary. The technical method remains documented in [Health methodology](health-methodology.md). The live status vocabulary is authoritative in the published health snapshot and the machine advertisements; this page must not become a source of current counts.

## Status table

| Status | What DataPulse observed | Evidence basis | Recommended human action | Recommended agent action | Do not infer |
|---|---|---|---|---|---|
| `fresh` | The source was reachable, structurally usable, and within the policy's freshness window | Content date, source metadata, or transport header measured against the declared cadence | Use for the declared purpose, while retaining the observation time and source citation | Cite with the status, observation time and licence attached; a currentness claim is permitted | Every value is substantively correct or current beyond the observation |
| `aging` | The source is usable but is older than its ordinary freshness window and not yet in the stale boundary | Content age beyond the ordinary window, inside the stale boundary | Review the age and cadence; use only when the tolerance is acceptable | Prefer a fresher alternative for a current claim; if used, state the age and the date | The source is broken or discontinued |
| `stale` | The source remains observable but is older than the permitted freshness boundary | Content age beyond the permitted boundary | Do not present it as current; seek a newer source or qualify the answer | Refuse a currentness claim; offer a fresher alternative, or present the figure as historical with its age | The publisher has stopped publishing |
| `discontinued` | The approved discontinuation evidence indicates that the source is no longer publishing or is explicitly retired | Approved discontinuation evidence, not content age | Do not use as a current source; inspect successor or archived references | Refuse, and point to a successor or archived reference when one is known | The source was discontinued merely because content is old |
| `degraded` | The source is reachable but a configured structural, schema, record-count, or integrity check failed | A named configured check failed against the recorded baseline | Stop or investigate the named failure before relying on it | Do not parse or cite the payload; surface the named failure instead | All values are wrong, or the source is unreachable |
| `browser-dependent` | Reliable observation requires rendered browser state or a browser-specific access path | The documented browser/evidence path is required for a reliable observation | Follow the documented browser path and inspect coverage | Do not treat a direct-request failure as publisher downtime; use the documented path or state the coverage limit | A direct request failure proves the publisher is down |
| `unreachable` | DataPulse could not access the source successfully under the probe policy | The probe could not reach the source under policy | Do not treat the source as currently usable; retry only under policy | Refuse a currentness claim; do not retry outside the probe policy | The source is permanently discontinued |
| `unknown` | The available evidence cannot establish a safe classification | Evidence is insufficient to classify safely | Preserve uncertainty and seek more evidence | State that no classification could be established; never substitute a neutral score or a default assumption | Unknown means fresh, stale, or a neutral score |
| `unknown-freshness` | The source is observable, but no reliable freshness signal was established | The source was reachable with no reliable date signal | Do not claim currentness; inspect source-specific date signals | Use for discovery; refuse a "latest" or "current" claim | The source is stale or discontinued |
| `reference` | The dataset is intentionally retained for context or an out-of-cadence use | Declared policy for a reference-family dataset | Use as reference under its stated purpose and date context | Cite as reference material with its date context; never as live operations data | The dataset should satisfy ordinary freshness expectations |

The reference family is refined by `data_type` without changing the status; that mapping belongs to [Health methodology](health-methodology.md).

## Status versus decision

A status describes observed source condition. A consumer decision is policy-specific.

For example:

- `fresh` may still be unsuitable for a safety-critical use;
- `aging` may be acceptable for a historical report;
- `unknown-freshness` may be usable for discovery but not for a "latest" claim;
- `reference` may be appropriate for background context but not live operations.

Do not replace the underlying status with a colour, score, or simplified chip. A presentation layer may add `use`, `warn`, `stop`, or `reference-use`, but the underlying status and reason remain visible.

## Freshness evidence hierarchy

Freshness is evaluated from available evidence, which may include:

1. content-level date signals;
2. explicit source metadata;
3. transport headers such as `Last-Modified`;
4. declared cadence and observation history.

A transport header can describe an upload or cache event rather than the newest record in the content. When content and header signals disagree, the policy must preserve the disagreement rather than silently choosing the more favourable result.

## Agent response rule

An agent answering from DataPulse should include:

- the source and publisher;
- the DataPulse status;
- the observation time;
- the relevant freshness or limitation signal;
- the licence/attribution context when reuse matters;
- a refusal or qualification when the evidence does not support a current claim.

A worked refusal example, using a real stale dataset, is in [Quickstart](quickstart.md).
