# Enterprise and governance guide

## Executive summary

DataPulse is a read-only source-observation and evidence layer for Malaysian public data. It helps an AI or data workflow determine what a publisher exposes, when it was observed, whether the source showed freshness or structural problems, what licence context was recorded, and what remains unknown.

It is not the source of record, a universal data-quality certification, a security admission controller, or a legal opinion.

## Governance questions

### What does DataPulse verify?

DataPulse verifies bounded, observable conditions such as reachability, response shape, freshness signals, schema/record observations, source metadata, provenance, and artifact integrity under named policies.

### What remains the publisher’s responsibility?

The publisher remains responsible for the underlying values, definitions, completeness, corrections, and official interpretation of its data.

### How should a customer use a positive status?

A positive status means the configured evidence satisfied a particular policy at an observation time. It should be combined with the intended use, source authority, licence, time scope, and any limitations.

### How should a customer use an unknown or negative status?

Preserve it. Unknown, stale, degraded, unreachable, and discontinued are decision-relevant states. They should trigger qualification, review, alternate sourcing, or refusal—not silent substitution.

### Does a signature certify the data?

No. A signature or digest can support artifact identity and integrity. It does not establish that an upstream value is true.

## Security boundary

The public DataPulse surface is read-only and does not require caller authentication for its public MCP contract. It should not be described as a scanner for arbitrary MCP server security, a runtime admission controller, or a guarantee against malicious or misleading source content.

Customers requiring private admission, access control, or organisation-specific policy need a separate consumer-side control plane. Public evidence and private enforcement must not be conflated.

## Licence and attribution boundary

DataPulse records available licence and attribution information from the source metadata or publisher terms. Consumers remain responsible for checking whether their intended use, redistribution, transformation, and jurisdiction are permitted.

Always cite the official publisher and preserve the recorded DataPulse observation when using a DataPulse classification in a report.

## Privacy and data handling

The public trust layer is designed around public source metadata and observations. Do not place credentials, private customer data, access tokens, cookies, or sensitive operational material in public evidence objects or documentation.

For current implementation-specific privacy details, consult the repository’s privacy and security policies rather than inferring them from this explanatory page.

## Procurement evidence checklist

A reviewer evaluating DataPulse should request:

- the trust contract;
- the current evidence receipt specification;
- a sample receipt and independent verification result;
- the health methodology and status semantics;
- release reproducibility evidence;
- source/licence coverage for the intended datasets;
- incident and correction handling;
- public endpoint and machine-advertisement verification;
- explicit limitations and support boundaries.

## Recommended contract wording

> DataPulse provides time-scoped, source-linked evidence about observable conditions of selected public-data sources. It does not replace the official publisher or certify substantive truth. Consumers remain responsible for deciding whether a source is fit for their use, legally reusable, and appropriate for the consequence of the decision.
