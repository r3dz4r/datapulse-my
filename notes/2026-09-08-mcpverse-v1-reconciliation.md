# 2026-09-08 — private MCPVerse v1 reconciliation

## Scope and result

This is a private, deterministic MCPVerse v1 benchmark lane. It adds no MCP tool, resource, route, runtime dependency, authentication, payment, or Engine surface. The 15-task fixture is evaluated offline by `mcp/agent_task_suite.py`; `mcp/score_agent_trace.py` accepts an independently supplied trace as explicit local input. Neither evaluator invokes a model, contacts an MCP endpoint, or makes a semantic-truth or quality-certification claim.

The fixture's intentional redundant-call task remains a failing negative case, demonstrating efficiency accounting rather than reporting an artificial all-pass result.

## Catalogue reconciliation

`mcp.json` is the generated canonical catalogue and reports 18 tools at this reconciliation point. The suite is a workflow/evidence benchmark, not a one-task-per-tool conformance matrix. Direct task workflows cover the four tools that establish a citation-ready pre-trust decision:

| Catalogue tool | Direct task coverage | Purpose exercised |
| --- | --- | --- |
| `search_datasets` | discovery, pre-trust selection, conflicts, out-of-catalogue, budget | discovery before reliance |
| `verify_dataset` | currentness, status outcomes, claims, conflicts | published fail-closed verification evidence |
| `get_evidence` | audit workflow and receipt binding | evidence receipt context |
| `get_provenance` | citations, licence/attribution, claim and reference handling | source/provenance and citation fields |

The remaining catalogue tools are reconciled but intentionally have no direct fixture invocation: `get_dataset` duplicates detail available in the selected pre-trust path; `find_stale`, `get_freshness_summary`, `find_anomalies`, `find_deteriorating`, `find_recovering`, `find_unreliable`, and `find_schema_drift` are discovery/risk views rather than a dataset-specific verification decision; `check_reconciliation` is contextual discrepancy evidence, not proof that either source is correct; `verify_evidence` is a live transport observation outside offline scoring; `trust_verdict` and `verify_attestation` provide attestation context but do not establish current availability or semantic truth; `find_by_licence` enumerates reuse scope while the lane exercises licence evidence on the selected citation; and `usage_summary` is aggregate analytics unrelated to an answer trace. This is deliberate non-coverage, not a claim that those tools are untested elsewhere.

The fixture/evidence tests cover discovery; verify-before-rely; provenance, citation, and receipt binding; licence handling; `fresh`, `aging`, `stale`, `discontinued`, `reference`, `unknown`, `unknown-freshness`, and `unreachable` outcomes; conflicting evidence; semantic-truth abstention; call budget and redundancy; and deterministic repeatability. `degraded` and `browser-dependent` remain fail-closed unsafe statuses in the answerability evaluator, rather than being promoted to a new task or status.

## Report and score semantics

The fixture report schema is `datapulse/v1/agent-task-suite-report`. Each row contains `task_id`, `passed`, explicit `outcome`/`action`/`reason`, call and redundancy counts, offline-verifier status, and five binary scores: workflow, outcome, citation, efficiency, and external verification. A row passes only at total `5`; aggregates expose task pass/fail counts, the four closed outcome counts (`supported`, `partial`, `unsupported`, `unknown`), call totals, redundant calls, and mean score. The external adapter uses the same report schema with `evaluation_mode: external_semantic`, permits documented citation field aliases and free-text reasons, but still fails a score where the declared workflow/outcome/action, receipt binding, or budget is not met.

Malformed trace shape, duplicate/missing/unknown task IDs, and malformed call lists are rejected before scoring. A missing required evidence receipt or an unrecognised outcome cannot pass. Explicit `unknown` plus `abstain` remains a valid scored result when it is the task contract; it is not converted into a successful answer.

## Limitations and dogfood boundary

Fixture results prove only deterministic conformance to supplied local contracts. They do not prove live-agent capability, user adoption, live upstream reachability, data accuracy, licence permission, semantic truth, or production quality.

Live dogfood is a separate, opt-in exercise: run an independent agent against the public MCP catalogue; retain raw tool-call trace and response evidence; redact secrets and personal data; save a complete explicit trace matching `datapulse/v1/agent-task-trace`; then score it locally with explicit `--suite` and `--trace` paths. Record agent/runtime/version, catalogue revision, timestamp, task selection, raw-trace location, score report, and human review separately from fixture reports. No live dogfood run or external agent trace was created by this reconciliation dispatch.

Failure traces may form a private regression corpus only after review and redaction. Any future public benchmark publication needs a separate operator decision covering methodology, corpus provenance, privacy, reproducibility, and wording; this note neither publishes a benchmark nor authorizes a public quality claim.
