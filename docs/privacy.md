# Data collection and privacy — DataPulse

**Scope:** the public lanes — the website at data-pulse.my, the read-only MCP server at mcp.data-pulse.my, and the published usage aggregate.

This statement describes what DataPulse collects, what it does not collect, and who is unavoidably able to observe a request. It is written to be checkable: every claim below names the artefact or code path that makes it true, so a reader does not have to take our word for it.

## What we do not collect

**No client identifiers.** The MCP usage ledger records one row per tool call and contains no IP address, no User-Agent, no cookie, no session identifier, and no client fingerprint. The recorded fields are exactly:

```
ts, schema_era, tool, args, call_id, process_instance_id,
result_summary, outcome, latency_ms, http_request_id
```

`call_id` is a freshly generated random UUID per call. `process_instance_id` identifies *our* server process, not the caller. The claim is enforced in code, not by convention: `mcp/server.py` declares `USAGE_LEDGER_SCHEMA_ERA = "anonymous-correlated"` and carries the standing rule *"Telemetry must never change the public anonymous HTTP contract."*

**No tracking on the website.** The public pages load no analytics or tag scripts — no Plausible, Google Analytics, Tag Manager, PostHog, Matomo, Umami, Segment, Mixpanel, or Cloudflare Insights — and access no cookies or browser storage. This is verifiable in the served HTML.

**No account, no key, no login.** The MCP endpoint requires no authentication by design. There is therefore no user identity to record even in principle.

## What we do collect

**Anonymous, aggregate usage.** For each tool call we record the fields listed above and publish an aggregate summary: total calls, calls by outcome, calls by tool, calls by dataset, and a trust-score distribution.

**Arguments are aggregated against the known catalogue.** A requested dataset id is counted under its own name only if it exists in the published catalogue. Any other value — a typo, a probe, an arbitrary string — is counted under a single `(unrecognised)` bucket and is **never republished**. This matters because the aggregate is public: without that rule, a caller could cause an arbitrary string to be published here under our name.

## What we cannot avoid observing

A transparency statement that claims nothing is observed would be false, so here is the boundary.

**The network sees the request.** DataPulse is served through Cloudflare. Cloudflare necessarily observes connection metadata, including the client IP address and User-Agent, in order to route and protect the request. That observation happens at the network edge, outside the DataPulse application, and applies to essentially every website on the internet. DataPulse's own code never receives or stores that information.

**One retained correlation handle.** The ledger keeps `http_request_id`, a Cloudflare request identifier, to correlate the calls belonging to a single exchange. It does not by itself identify a client, but it is a handle, and it is named here rather than omitted because a disclosure that hides the one client-adjacent field would not be honest.

**Aggregate statistics are public.** The usage summary is published. It contains counts and no client-identifying values, but it is public.

## Why it is built this way

DataPulse exists to make official Malaysian public data trustworthy and checkable. A transparency layer that quietly tracked its readers would contradict its own purpose, so the public lane is deliberately untracked even where tracking would be commercially useful. The trade is accepted knowingly: we get less information about our audience, and in exchange anyone can audit the claim rather than trust it.

## Verifying these claims

- The ledger record shape and the anonymous-contract rule: `mcp/server.py` — the usage middleware, `USAGE_LEDGER_SCHEMA_ERA`, and the `(unrecognised)` bucketing in the `usage_summary` handler.
- The absence of website trackers: fetch any public page and search the HTML for script tags and cookie access; there are none.
- The published aggregate itself: the `usage_summary` tool on the public MCP endpoint.

## Changes to this statement

If what we collect changes, this statement changes in the same commit, and the code and the disclosure move together. A privacy claim that lags the implementation is worse than no claim at all.
