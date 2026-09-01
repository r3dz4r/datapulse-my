# Trust contract

## What DataPulse is

DataPulse is a read-only evidence and verification layer for Malaysian public-data sources. It observes what an upstream source exposes, records the available evidence, classifies source condition under a named policy, and makes that evidence readable by people and machines.

DataPulse does not replace the publisher. The upstream publisher remains the source of record for the underlying values.

## What DataPulse can establish

Depending on the source and available signals, DataPulse can establish bounded facts such as:

- a source was reachable or not reachable at an observation time;
- a response had a particular content type or transport result;
- content exposed a parseable publication or data date;
- a response’s structure, schema, or record count changed;
- a source was classified under the current health policy;
- a licence or attribution statement was recorded from the available metadata;
- an evidence artifact or release matched a stated digest or signature check;
- a claim has a documented lineage to an observation or artifact.

Each statement must remain scoped to its subject, observation time, method, policy, and evidence coverage.

## What DataPulse cannot establish by observation alone

DataPulse cannot establish that:

- an upstream value is substantively true in the real world;
- a publisher’s source is complete, unbiased, or fit for every purpose;
- a recent HTTP response contains recent data;
- a valid signature makes a dataset correct;
- a source is legally reusable beyond the licence evidence recorded;
- a tool or MCP server is secure merely because its response has provenance;
- a current snapshot proves what was available at an earlier date;
- missing evidence should be treated as a pass or a neutral score.

## Evidence layers

| Layer | Question answered | Does not answer |
|---|---|---|
| Transport | Could DataPulse access the source? | Is the data correct? |
| Content | What did the response contain? | Is the content truthful? |
| Freshness | What date/change signal was observable? | Is the source current in every semantic sense? |
| Structure | Did the response match the expected shape? | Are individual values accurate? |
| Licence | What reuse terms were recorded? | Is a downstream use legally safe in every jurisdiction? |
| Provenance | Where did this artifact or claim come from? | Does lineage make it true? |
| Integrity | Did the bytes/identity match the expected digest or signature? | Was the source honest? |
| Human review | Who reviewed the stated evidence under which policy? | Does the reviewer’s decision make the source objectively true? |

## Unknown is a result

DataPulse uses explicit unknown or indeterminate outcomes when evidence is missing, conflicting, inaccessible, or not safely interpretable. Consumers must preserve that uncertainty.

A consumer must not convert:

- missing freshness into fresh;
- missing licence into permitted reuse;
- a failed verification into a successful one;
- a stale source into discontinued without the required evidence;
- a generated score into a universal quality judgement.

## Read-only boundary

DataPulse observes and publishes evidence. It does not write to upstream publishers, correct upstream records, or silently replace missing data with estimates. If a use case requires upstream mutation, it belongs to a different system and contract.

## How to cite DataPulse correctly

Prefer statements such as:

> DataPulse observed the source at `<timestamp>` and classified it as `<status>` under `<policy/version>`.

> The publisher declares `<fact>`; DataPulse independently observed `<signal>` at `<timestamp>`.

> The evidence artifact verifies the integrity of these bytes, but does not establish the substantive truth of the upstream values.

Avoid statements such as:

> DataPulse certifies that this dataset is true.

> This dataset is verified, therefore every value is accurate.

> The source is fresh because the endpoint returned HTTP 200.

## Related contracts

- [Status semantics](status-semantics.md)
- [Evidence receipt specification](evidence-receipt-spec.md)
- [Dataset lifecycle](dataset-lifecycle.md)
- [Reproducibility](reproducibility.md)
- [Glossary](glossary.md)
