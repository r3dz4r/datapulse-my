# `record-evidence/v1`

## Objective

`record-evidence/v1` is DataPulse MY's record-level trust contract. It turns a
tabular source observation into independently inspectable row classifications
without changing the existing dataset-health contract. The first and only
pilot is `pharmaceutical_products`; additional verticals require a separate
review.

The JSON Schema is [`record-evidence.schema.json`](../record-evidence.schema.json).

## Envelope

Every full and excerpt envelope has these fields:

```json
{
  "schema": "record-evidence/v1",
  "dataset_id": "pharmaceutical_products",
  "observed_at": "2026-08-12T12:14:07Z",
  "run_date": "2026-08-12",
  "source_url": "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv",
  "source_sha256": "64 lowercase hex characters",
  "record_count": 28073,
  "schema_valid_count": 28073,
  "freshness": {
    "source_last_modified": "2026-08-08T09:55:45Z",
    "age_days": 4,
    "status": "stale"
  },
  "status_distribution": {
    "fresh": 0,
    "aging": 0,
    "stale": 28073,
    "discontinued": 0,
    "degraded": 0,
    "browser-dependent": 0,
    "unreachable": 0,
    "unknown": 0,
    "unknown-freshness": 0,
    "reference": 0
  },
  "records": []
}
```

The full record list is written to
`record-evidence/<dataset_id>/<run_date>.json`. `latest.json` has the same
envelope but contains a deterministic, status-representative excerpt of at
most 50 records. Consumers must use `record_count`, not `records.length`, as
the population size.

## Record explanations

Each record has `record_id`, `status`, `explanation`, and `evidence_digest`.
The explanation contains:

- `freshness`: the source-level last-modified instant and whole-calendar-day
  age used for the row classification;
- `structural`: whether the row has the CSV header width, a usable identifier,
  and any pilot-specific identifier shape;
- `linkage`: typed pointers derived from identifiers present in the row plus
  labels for relationships that could not be pointed to;
- `alternatives`: record pointers for a discontinued item, empty in the
  products-only pilot because cancelled registrations are not ingested here.

For the NPRA pilot, `reg_no` is the primary key and the accepted shape is
case-insensitive `MAL` + eight digits + one or more letters. Duplicate upstream
registration numbers retain the first `reg_no:<value>` identifier and receive
deterministic `#2`, `#3`, … occurrence suffixes. Linkage pointers use the
source's OSA codes (`osa_code:<value>`); they are evidence-bearing candidate
pointers, not claims that another vertical record was resolved.

Generic CSVs use `record_id`, `id`, `reg_no`, or `license_no` when present,
then the first column, with `row:<number>` as the final fallback. Generic rows
must have the parsed header width and a non-empty chosen identifier. A vertical
can add reviewed identifier rules without changing the envelope.

## Status taxonomy

The distribution always contains all ten keys, including zero counts:

| Status | Record-level meaning |
| --- | --- |
| `fresh` | Structurally usable and within the source cadence window. |
| `aging` | Structurally usable, older than the cadence window, and no older than three windows. |
| `stale` | Structurally usable and older than three cadence windows. |
| `discontinued` | The record or source has explicit discontinuation evidence. |
| `degraded` | The row fails structural validation. |
| `browser-dependent` | Verification requires rendered browser state. |
| `unreachable` | The source observation could not be retrieved. |
| `unknown` | No reliable classification evidence is available. |
| `unknown-freshness` | Structurally usable, but no source modification time is available. |
| `reference` | A historical lookup record for which current freshness does not apply. |

The pilot ports the pharma engine's `STATUSES` tuple and its products cadence:
one day is fresh, two to three days is aging, and more than three days is
stale. These small constants are local by design. Importing `engine.pharma`
would couple DataPulse production to a sibling checkout, its Python path, and
its venv.

## Freshness and digest rules

`source_last_modified` is normalized to UTC ISO 8601. `age_days` is the
non-negative difference between its UTC calendar date and `run_date`; a future
timestamp is rejected. When the HTTP response supplies no defensible
last-modified value, both fields are `null`/`unknown-freshness` as appropriate.

`evidence_digest` is `sha256:` followed by the lowercase SHA-256 of the UTF-8
RFC-style canonical JSON serialization of the `explanation` object: keys
sorted, no insignificant whitespace, and Unicode retained. It excludes
`observed_at`, row position, and envelope metadata, so the same explanation
always has the same digest. `source_sha256` is the lowercase SHA-256 of the raw
CSV response bytes before decoding.

## Validation and boundaries

The strict validator enforces the JSON Schema, the ten exact distribution
keys, `sum(status_distribution) == record_count`,
`schema_valid_count <= record_count`, record/digest consistency, and full-file
record cardinality. The latest excerpt is explicitly exempt from full-file
cardinality.

This pilot does not ingest the cancelled-products table, resolve company names
across NPRA licence tables, or define record/graph diffs. Those are follow-up
contracts after the pilot is evaluated.
