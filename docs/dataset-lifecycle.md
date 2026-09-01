# Dataset lifecycle

This is the source-maintainer contract for adding, changing, diagnosing, reconciling, and retiring a DataPulse dataset.

## Lifecycle states

A dataset may be:

1. proposed;
2. onboarded;
3. observed;
4. degraded or under investigation;
5. superseded or merged;
6. discontinued;
7. archived.

A health status is not the same thing as a lifecycle state. For example, a live source may be stale without being discontinued.

## Onboarding checklist

Before adding a dataset:

- identify the official publisher and source of record;
- verify the canonical source URL and any redirect/alternate route;
- assign a stable identifier without silently normalising upstream tokens;
- record licence and attribution evidence;
- define expected response type, schema, and record-count behaviour;
- record declared cadence and observable freshness signals;
- determine whether browser access is required;
- create the metadata/source description;
- establish a sample and schema baseline;
- define the probe policy and failure mapping;
- add required manifest/configuration entries;
- generate JSON/JSON-LD, badges, dashboard, discovery, and MCP references through their owner scripts;
- add focused tests and fixtures;
- run repository and release invariants;
- verify the served route and evidence shape.

The manifest is not the whole addition contract. Auxiliary policy, metadata, generated envelopes, dashboard/discovery references, and contract tests must remain aligned.

## Updating a source

When an upstream source changes:

1. preserve the prior observation and evidence;
2. record the change type and source evidence;
3. update the source contract or probe policy only when the new behaviour is verified;
4. update the schema/baseline deliberately;
5. classify the interim state honestly;
6. regenerate owned outputs;
7. run focused tests and release invariants;
8. verify the public and machine surfaces.

Do not hide a source change by overwriting history or widening a parser until the new behaviour has been inspected.

## Reconciliation rules

When signals disagree, preserve both sides:

- publisher-declared metadata is labelled `publisher_declared`;
- probe observations are labelled `observed`;
- policy decisions are labelled `derived`;
- unresolved conflicts remain `disputed` or `unknown`;
- a later correction links with `supersedes` rather than reusing the old identity.

A recent upload header must not automatically override an ancient content date. A successful transport response must not automatically override a failed structural check.

## Schema and record-count changes

Treat changes as:

- **additive:** new fields that do not break declared consumers;
- **breaking:** removed, renamed, or type-incompatible fields;
- **semantic:** the shape remains similar but field meaning changed;
- **anomalous:** record count or response size changes outside the source’s known behaviour;
- **indeterminate:** evidence is insufficient to classify safely.

A source may remain reachable while being degraded. Consumers must see the reason rather than a generic green result.

## Merge and deduplication

Before merging records:

1. verify the deduplication premise against the live manifest;
2. identify the actual upstream identity field;
3. choose the surviving row using a documented rule;
4. preserve aliases and successor relationships;
5. cascade the change into policy/configuration, health, metadata, JSON, JSON-LD, badges, dashboard, MCP, and tests;
6. run the repository contract before release.

Do not assume the visible DataPulse ID is the upstream identity.

## Retirement rules

A dataset may be classified as discontinued only when the approved evidence supports it, such as an explicit retirement flag or an appropriate upstream failure. Old content by itself is not sufficient.

On retirement:

- preserve the last known evidence;
- record the retirement reason and date;
- link a successor if one exists;
- retain historical identifiers and aliases;
- update discovery and consumer guidance;
- regenerate all owned surfaces;
- verify that the public explanation matches the machine status.

## Reporting a correction

A correction report should include:

- dataset ID and source URL;
- what was expected;
- what was observed;
- observation time;
- evidence or reproduction steps;
- impact on the classification or claim;
- whether the issue is temporary, source-specific, or systemic.

Do not ask a reporter to prove more than is needed to reproduce the claim, and do not silently discard a challenge because the current dashboard is green.
