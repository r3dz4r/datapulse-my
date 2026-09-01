# Incident response

Use this runbook when DataPulse’s observed state, generated surfaces, deployed surfaces, or evidence claims may be wrong or unavailable.

## Incident principles

- Preserve evidence before changing the classification.
- Separate source failure, probe failure, generator failure, deployment failure, and documentation drift.
- Fail closed: do not turn missing evidence into a positive result.
- Do not overwrite historical evidence to make the current state look clean.
- A green CI job is not proof that the served surface is correct.

## First-response sequence

1. Record the first observed time and the user-visible symptom.
2. Read the current health artifact and its checked timestamp.
3. Inspect the relevant source, response shape, and headers directly where safe.
4. Check the pipeline/service log and timer state.
5. Compare generated local output with the canonical source.
6. Check public route status, content type, effective URL, and response body shape.
7. Classify the incident before applying a fix.
8. Preserve a dated incident record and relevant digests.

## Incident classes

### Health snapshot stale

Check whether the timer ran, whether the probe was due, whether the output mtime changed, and whether the pipeline failed before publication. Do not reclassify datasets merely because the snapshot is old.

### Source reachable but status wrong

Compare transport, content date, schema, record count, cadence, and policy input separately. Probe output is a symptom, not a diagnosis. A `no-header` signal does not by itself prove that an endpoint is dead.

### Dashboard/API/MCP mismatch

Compare the canonical input, generated artifact, deployed response, and served source identity. Identify which surface is stale rather than editing the visible output directly.

### Receipt route returns HTML or incomplete data

Verify content type, effective URL, body schema, and coverage. Either repair the route or narrow the public claim. Do not describe an HTML landing page as a machine-readable receipt.

### Schema or record-count anomaly

Preserve the response digest and baseline comparison. Classify additive, breaking, semantic, anomalous, or indeterminate change. Quarantine downstream use when the intended contract is no longer established.

### Attestation or digest verification failure

Treat the covered artifact as unverified. Check subject identity, payload bytes, digest scope, trust root, validity window, and supersession. Do not replace a failed verification with a new signature without understanding the mismatch.

### Generated-document drift

Identify the owning generator and whether the file is hand-authored, generated, or immutable history. Regenerate from the source; never patch a generated output merely to make a check pass.

## Containment options

Use the smallest safe containment:

- preserve the last known good artifact;
- mark the affected source degraded, stale, unreachable, or unknown under policy;
- remove an unsupported claim from public copy;
- quarantine a broken route;
- block release when an invariant fails;
- defer a source-specific repair while keeping the limitation visible.

Do not broaden scope into unrelated redesign, coverage expansion, payment, or private infrastructure work.

## Recovery verification

Recovery is complete only when:

- the source or pipeline symptom is understood;
- the intended fix is in the canonical input or generator;
- focused tests pass;
- repository and release invariants pass;
- generated output is deterministic;
- public routes return the expected content type and schema;
- source identity and evidence digests match;
- the served state has been read back;
- the incident record names remaining uncertainty.

## Postmortem minimum

Record:

- user-visible impact;
- expected versus observed behaviour;
- detection path and detection gap;
- root cause;
- why existing gates missed it;
- containment and recovery;
- public claim impact;
- regression test or new invariant;
- served-state verification;
- remaining limitations.

## Escalation boundaries

Stop and surface the issue before proceeding when the proposed response would:

- change the status taxonomy;
- alter a public evidence or attestation contract;
- rotate keys or trust roots;
- change authentication or access policy;
- delete historical evidence;
- modify upstream data;
- publish an external communication;
- absorb unrelated dirty files.
