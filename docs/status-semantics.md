# Status semantics

This page is the compact consumer contract for the current DataPulse health vocabulary. The technical method remains documented in [Health methodology](health-methodology.md). The live status vocabulary is authoritative in `health/latest.json` and the machine advertisements; this page must not become a source of current counts.

## Status table

| Status | What DataPulse observed | Recommended consumer action | Do not infer |
|---|---|---|---|
| `fresh` | The source was reachable, structurally usable, and within the policy’s freshness window | Use for the declared purpose, while retaining the observation time and source citation | Every value is substantively correct or current beyond the observation |
| `aging` | The source is usable but is older than its ordinary freshness window and not yet in the stale boundary | Review the age and cadence; use only when the tolerance is acceptable | The source is broken or discontinued |
| `stale` | The source remains observable but is older than the permitted freshness boundary | Do not present it as current; seek a newer source or qualify the answer | The publisher has stopped publishing |
| `discontinued` | The approved discontinuation evidence indicates that the source is no longer publishing or is explicitly retired | Do not use as a current source; inspect successor or archived references | The source was discontinued merely because content is old |
| `degraded` | The source is reachable but a configured structural, schema, record-count, or integrity check failed | Stop or investigate the named failure before relying on it | All values are wrong, or the source is unreachable |
| `browser-dependent` | Reliable observation requires rendered browser state or a browser-specific access path | Follow the documented browser/evidence path and inspect coverage | A direct request failure proves the publisher is down |
| `unreachable` | DataPulse could not access the source successfully under the probe policy | Do not treat the source as currently usable; retry only under policy | The source is permanently discontinued |
| `unknown` | The available evidence cannot establish a safe classification | Preserve uncertainty and seek more evidence | Unknown means fresh, stale, or a neutral score |
| `unknown-freshness` | The source is observable, but no reliable freshness signal was established | Do not claim currentness; inspect source-specific date signals | The source is stale or discontinued |
| `reference` | The dataset is intentionally retained for context or an out-of-cadence use | Use as reference under its stated purpose and date context | The dataset should satisfy ordinary freshness expectations |

## Status versus decision

A status describes observed source condition. A consumer decision is policy-specific.

For example:

- `fresh` may still be unsuitable for a safety-critical use;
- `aging` may be acceptable for a historical report;
- `unknown-freshness` may be usable for discovery but not for a “latest” claim;
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
