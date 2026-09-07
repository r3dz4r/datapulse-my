# 2026-09-08 — deterministic local agent-task suite

## Intent

`mcp/agent_task_suite.py` is an offline, fixture-driven readiness evaluator for
whether an agent follows DataPulse's source-verification workflow. It does not
call an LLM, network service, or public MCP endpoint, and it does not alter any
published MCP or generated surface.

## Task taxonomy

The initial 15 checked-in tasks exercise discovery; search/verification/
provenance selection; receipt-to-citation binding; supported, partial,
unsupported, and unknown outcomes; stale, discontinued, unreachable,
reference, and unknown-freshness handling; conflicting observations;
malformed/out-of-catalogue requests; redundant-call accounting; and the
existing external verifier's offline self-test.

Each task carries a user prompt, bounded acceptable call sequences, an exact
outcome/action/reason, citation and receipt-binding requirements, and a call
budget. Correctness is comparison against those fields only: no semantic model
judgement is used.

## Metrics and execution

The report schema is `datapulse/v1/agent-task-suite-report`. Per-task scores
cover workflow, outcome, citation, efficiency, and offline external-verifier
execution. Aggregates expose pass/fail counts, explicit outcome counts,
call totals, redundant calls, and mean score.

Run locally:

```bash
python3 mcp/agent_task_suite.py mcp/tests/fixtures/agent_task_cases.json
python3 -m pytest mcp/tests/test_agent_task_suite.py -q
```

## Baseline limitation

This benchmark measures capability readiness against deterministic local task
traces. It is not proof of independent external adoption, user activity,
revenue, or production agent behavior. The included redundant-call trace is an
intentional negative efficiency baseline, so the aggregate records one failure
rather than hiding it.
