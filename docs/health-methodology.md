# Health methodology

DataPulse MY reports evidence, not a promise that upstream data is correct.

## Status taxonomy

| Status | Meaning |
| --- | --- |
| `fresh` | Reachable, structurally usable, and within the freshness window. |
| `aging` | Freshness age is over 1.5× cadence and at most 3× cadence. |
| `stale` | Freshness age is over 3× cadence. |
| `degraded` | Reachable, but schema/shape or record-count checks failed. |
| `browser-dependent` | Assessment requires rendered browser state. |
| `unreachable` | The source request failed or returned non-2xx. |
| `unknown` | No reliable classification is available. |
| `unknown-freshness` | Reachable and structurally usable, but no freshness evidence exists. |

## Freshness and reachability

Reachability is not freshness. The probe chooses the newest defensible signal
from an HTTP `Last-Modified` header or parsed content date. Daily, weekly,
monthly, quarterly, and annual cadences use 1, 7, 30, 90, and 365-day baselines.
Future content dates are rejected. A 200 response without either signal becomes
`unknown-freshness`, not `fresh`.

BNM content dates are date-only. The dashboard adds the MYT time declared in
each manifest `refresh_frequency` for display; that time is presentation
metadata, not a timestamp parsed from the response.

## Content integrity

Record counts are compared with `expected_record_count` when it is known. A
result below half the expectation is degraded; capped or estimated results are
marked incomplete. Column-count or first-row-shape changes are also degraded so
schema drift cannot appear green.

Browser-backed sources always remain `browser-dependent`, even after a
successful Camofox snapshot. In due mode, unprobed rows and a previous
`last_checked` value are preserved. A probe that produces no measurement does
not erase the last successful measurement.

## Blind spots

- HTTP and sampled content checks do not prove semantic accuracy or completeness.
- Generic row counting can be fooled by undocumented pagination or wrappers.
- Browser snapshots depend on client rendering, timing, and selector-free text.
- A stable first-row hash cannot detect changes elsewhere in a dataset.
- Licence and attribution are verified metadata, not legal advice.
