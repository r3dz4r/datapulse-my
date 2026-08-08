# Canonical derived-JSON workspace proposal

Date: 2026-08-08  
Status: Design proposal; no implementation is included

## 1. Executive summary

`data/json/<id>.json` should become the single canonical per-dataset machine-readable artifact, replacing both the heterogeneous legacy envelopes in `data/json/` and the separate per-dataset JSON-LD files in `data/jsonld/`. Each file should have one versioned, validated shape that combines stable registry metadata, editorial manifest metadata, probe policy, the latest normalized health observation, structural profile, provenance, and a JSON-LD identity. Both `pharmaceutical_*` and `npra_*` IDs should remain first-class and distinct even when they share an upstream file, with an explicit relationship describing shared source rather than an alias or redirect between identities. A deterministic generator should rebuild every canonical dataset file and the catalog after every successful 15-minute timer cycle, using content-derived freshness first and approved cadence-specific fallbacks and windows. All generated DataPulse links should use `https://data-pulse.my`, while official upstream source URLs remain unchanged as provenance and retrieval targets.

## 2. Current state inventory

This inventory is from the checked-out repository on 2026-08-08. Counts are observations, not constants to embed in code; generators and verifiers must calculate them from their inputs on every run.

| Path | Live state | Current role and shape | Problem for a canonical workspace |
| --- | ---: | --- | --- |
| `datapulse.json` | 166 registry rows | Public registry and scheduling input. Rows hold identity, source URL, steward, licence, cadence, namespace, expected count, report path, and verification metadata. | It excludes the three current `npra_*` report manifests, so it cannot yet express locked G1 by itself. |
| `data/*.md` | 169 report manifests | Hand-maintained Markdown with YAML front matter plus narrative sections. The front matter is not uniform: older reports use `dataset_id`, while newer reports often contain both `id` and `dataset_id`; useful schema detail sometimes exists only in Markdown tables or prose. | These are the human/editorial source of truth, but their machine-readable fields need normalization before deterministic JSON generation. |
| `data/json/*.json` | 92 files | Legacy per-dataset envelopes. There are four observed top-level shapes: 81 files share the main health-envelope shape, eight omit its top-level `schema`, and three are source-specific variants. Fields include status, checks, data fields, reproducibility, quirks, and licence. | Coverage is partial (74 registry IDs have no file), status values include older terms such as `healthy` and `current`, timestamps lag live health, and shape varies by dataset. No `pharmaceutical_*` or `npra_*` file exists here. |
| `data/jsonld/*.json` | 167 files | 166 schema.org per-dataset JSON-LD files plus `catalog.json`. Per-dataset files have one consistent schema.org-oriented shape and are generated from `datapulse.json` plus `health/latest.json`. | This is a second per-dataset representation, its IDs only match the 166-row registry, and its location conflicts with G2's one canonical derived workspace. |
| `health/latest.json` | 166 health rows | Generated `datapulse/v0.3/dataset-health` full-cycle or due-merge snapshot, with `_trust_summary` and one detailed observation per registry ID. | This is the correct cycle snapshot and should remain, but it currently has no `npra_*` rows and is regenerated separately from per-dataset reports and JSON artifacts. |
| `badges/` | 166 dataset SVGs, six status SVGs, and an index | Generated presentation artifacts derived from health state. | Dataset badge coverage follows the current registry and therefore excludes `npra_*`. Badges are views, not canonical data. |

### Manifest examples and authority

The live reports show why the generator must merge explicit authorities rather than infer everything from one file:

- `data/pharmaceutical_products.md` supplies the title, licence, attribution, source URL, 16-column description, known quirks, and narrative provenance. Its live front matter says monthly cadence and `fresh`.
- `data/npra_products_registered.md` intentionally points to the same upstream CSV but defines a paid-product provenance scope, daily cadence, registration-format compatibility rule, and different quirks. It must remain a separate ID under G1.
- `data/dgm_blood_donations_state.md` uses the older `dataset_id`-first front-matter shape and carries rich schema and caveat text.
- `data/met_weather.md` demonstrates nested field structure and a rolling forecast where the earliest forecast date, rather than the maximum date, is the content freshness signal.

The following field-authority order avoids circular generation:

| Information | Authoritative input | Notes |
| --- | --- | --- |
| Canonical ID, registry membership, name, source, steward, licence, portfolio namespace, expected count, cadence label | `datapulse.json` | Add the three preserved `npra_*` identities before canonical generation covers them. Do not derive IDs from filenames alone. |
| Editorial description, attribution, known quirks, breaking changes, field definitions, special scope | Normalized YAML front matter in `data/<id>.md` | During migration, promote structured facts currently present only in prose/tables or legacy JSON into front matter. The generator must not scrape arbitrary prose. |
| Probe adapter, content-date field, selector, rolling behavior, special validation, due interval | The validated internal probe-policy document proposed by PLAN A1 | This is implementation policy, not copied out of shell maps. Its keys must be a subset of registry IDs. |
| Latest observations and classification | Normalized probe output and the resulting `health/latest.json` row | Status must be computed once by the pure classifier proposed by PLAN A2, not independently by each output generator. |
| Derived URLs, JSON-LD projection, generation time, input digests | Canonical JSON generator | DataPulse URLs always use `https://data-pulse.my`; source URLs retain their official hosts. |

## 3. Proposed target structure

```text
data/
├── <id>.md                         # keep: human/editorial source manifest
└── json/
    ├── schema.json                 # JSON Schema for every <id>.json
    ├── context.json                # JSON-LD context for the same documents
    ├── catalog.json                # generated index/JSON-LD DatasetCatalog
    └── <id>.json                   # one canonical derived document per registry ID

health/
└── latest.json                     # keep: atomic all-dataset operational snapshot

config/ (exact existing/new policy directory may be chosen during implementation)
└── probe-policy.json               # validated internal input, not a public derived artifact
```

The three reserved filenames `schema`, `context`, and `catalog` must be forbidden as dataset IDs. No per-dataset output remains under `data/jsonld/`; `data/json/<id>.json` is JSON-LD-compatible itself through `@context`, `@type`, and `@id`. `health/latest.json` is not a competing canonical per-dataset path: it is the atomic cycle snapshot used to prevent readers from observing a mixture of cycles and to support efficient portfolio-wide polling. `catalog.json` indexes canonical files and embeds only a compact schema.org projection; it must not duplicate the complete per-dataset documents.

Canonical generated URLs are:

```text
https://data-pulse.my/data/json/<id>.json
https://data-pulse.my/data/json/catalog.json
https://data-pulse.my/data/json/schema.json
https://data-pulse.my/data/json/context.json
https://data-pulse.my/data/<id>.md
https://data-pulse.my/health/latest.json
https://data-pulse.my/badges/<id>.svg
```

Official retrieval URLs such as `https://storage.data.gov.my/...` are deliberately preserved in `source.distributions`; G7 governs DataPulse-owned generated references, not upstream provenance.

## 4. `data/json/<id>.json` schema

### Contract conventions

- Contract identifier: `datapulse/dataset/v1`.
- JSON Schema URI: `https://data-pulse.my/data/json/schema.json`.
- JSON-LD context URI: `https://data-pulse.my/data/json/context.json`.
- Field names use `snake_case`, matching `datapulse.json` and `health/latest.json` and avoiding a repository-wide casing migration.
- Every canonical file has the same top-level shape. Inapplicable measurements are `null`; keys do not appear and disappear based on adapter type.
- Dates use RFC 3339 full-date (`YYYY-MM-DD`) and timestamps use UTC RFC 3339 date-time (`YYYY-MM-DDTHH:MM:SSZ`). Durations and thresholds use integer seconds, not prose or floating-point days.
- Arrays are deterministically ordered: distributions by `role` then URL, fields in source order, relationships by ID, and changes/quirks in manifest order.
- `generated_at` changes on every successful health-cycle generation, as required by G6. Stable content remains stable except for this generation metadata and cycle-derived health values.
- Unknown numeric values are `null`, never `0`; an actual zero measurement remains `0`.

### Full JSON Schema-like definition

The definition below is intentionally implementation-ready. It uses JSON Schema 2020-12 vocabulary plus comments for cross-field rules that ordinary JSON Schema cannot express cleanly.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://data-pulse.my/data/json/schema.json",
  "title": "DataPulse MY canonical dataset document",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "$schema",
    "schema_version",
    "@context",
    "@type",
    "@id",
    "id",
    "name",
    "description",
    "generated_at",
    "canonical_url",
    "report_url",
    "identity",
    "source",
    "publication",
    "health",
    "data_profile",
    "change_control",
    "links",
    "generation"
  ],
  "properties": {
    "$schema": {
      "const": "https://data-pulse.my/data/json/schema.json"
    },
    "schema_version": {
      "const": "datapulse/dataset/v1"
    },
    "@context": {
      "const": "https://data-pulse.my/data/json/context.json"
    },
    "@type": {
      "const": "Dataset"
    },
    "@id": {
      "$ref": "#/$defs/canonical_dataset_url"
    },
    "id": {
      "$ref": "#/$defs/dataset_id"
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "description": {
      "type": "string",
      "minLength": 1
    },
    "generated_at": {
      "$ref": "#/$defs/timestamp"
    },
    "canonical_url": {
      "$ref": "#/$defs/canonical_dataset_url"
    },
    "report_url": {
      "type": "string",
      "format": "uri",
      "pattern": "^https://data-pulse\\.my/data/[A-Za-z0-9_-]+\\.md$"
    },
    "identity": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id_namespace", "portfolio_namespace", "scope", "related_datasets"],
      "properties": {
        "id_namespace": {
          "type": "string",
          "minLength": 1,
          "$comment": "The semantic ID family, e.g. pharmaceutical or npra. Do not collapse these two values. For legacy unprefixed IDs, use the approved registry family rather than guessing from the first token."
        },
        "portfolio_namespace": {
          "type": ["string", "null"],
          "$comment": "The existing datapulse.json namespace/category, distinct from id_namespace."
        },
        "scope": {
          "type": "string",
          "minLength": 1
        },
        "related_datasets": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["id", "relation", "canonical_url"],
            "properties": {
              "id": { "$ref": "#/$defs/dataset_id" },
              "relation": {
                "enum": [
                  "same-source-distinct-scope",
                  "supersedes",
                  "is-superseded-by",
                  "derived-from",
                  "companion"
                ]
              },
              "canonical_url": { "$ref": "#/$defs/canonical_dataset_url" }
            }
          }
        }
      }
    },
    "source": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "source_name",
        "steward",
        "publisher",
        "landing_page_url",
        "distributions",
        "licence",
        "attribution",
        "geo_coverage",
        "is_accessible_for_free"
      ],
      "properties": {
        "source_name": { "type": "string", "minLength": 1 },
        "steward": { "type": "string", "minLength": 1 },
        "publisher": { "type": "string", "minLength": 1 },
        "landing_page_url": {
          "type": ["string", "null"],
          "format": "uri"
        },
        "distributions": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["role", "url", "media_type", "access_method"],
            "properties": {
              "role": {
                "enum": ["primary", "alternate", "lookup", "landing-page", "api"]
              },
              "url": { "type": "string", "format": "uri" },
              "media_type": { "type": ["string", "null"] },
              "access_method": {
                "enum": ["direct", "api", "browser", "discovery"]
              }
            }
          }
        },
        "licence": {
          "type": "object",
          "additionalProperties": false,
          "required": ["name", "url"],
          "properties": {
            "name": { "type": "string", "minLength": 1 },
            "url": { "type": ["string", "null"], "format": "uri" }
          }
        },
        "attribution": { "type": "string", "minLength": 1 },
        "geo_coverage": { "type": "string", "minLength": 1 },
        "is_accessible_for_free": { "type": ["boolean", "null"] }
      }
    },
    "publication": {
      "type": "object",
      "additionalProperties": false,
      "required": ["refresh_frequency", "freshness_policy"],
      "properties": {
        "refresh_frequency": {
          "type": "string",
          "minLength": 1,
          "$comment": "Original human-readable registry value."
        },
        "freshness_policy": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "cadence_class",
            "mode",
            "probe_interval_seconds",
            "baseline_seconds",
            "thresholds",
            "signal_policy"
          ],
          "properties": {
            "cadence_class": {
              "enum": [
                "realtime",
                "hourly",
                "daily",
                "weekly",
                "monthly",
                "quarterly",
                "annual",
                "survey-year",
                "as-required"
              ]
            },
            "mode": {
              "enum": ["fixed-window", "survey-year", "as-required"]
            },
            "probe_interval_seconds": {
              "type": "integer",
              "minimum": 1
            },
            "baseline_seconds": {
              "type": ["integer", "null"],
              "minimum": 1
            },
            "thresholds": {
              "type": "object",
              "additionalProperties": false,
              "required": ["fresh_lte_seconds", "aging_lte_seconds", "stale_gt_seconds"],
              "properties": {
                "fresh_lte_seconds": { "type": ["integer", "null"], "minimum": 0 },
                "aging_lte_seconds": { "type": ["integer", "null"], "minimum": 0 },
                "stale_gt_seconds": { "type": ["integer", "null"], "minimum": 0 }
              },
              "$comment": "For fixed-window cadences these are baseline × 1.5, baseline × 3, and baseline × 3. Realtime/hourly therefore use the actual source cadence rather than a one-day floor."
            },
            "signal_policy": {
              "type": "object",
              "additionalProperties": false,
              "required": [
                "content_date_field",
                "content_date_selector",
                "precedence",
                "fallback_on",
                "ignore_last_modified"
              ],
              "properties": {
                "content_date_field": { "type": ["string", "null"] },
                "content_date_selector": {
                  "enum": ["maximum", "minimum", "publisher-explicit", null]
                },
                "precedence": {
                  "type": "array",
                  "items": {
                    "enum": ["content-date", "last-modified", "last-checked"]
                  },
                  "uniqueItems": true,
                  "minItems": 1
                },
                "fallback_on": {
                  "type": "array",
                  "items": {
                    "enum": ["not-configured", "missing", "parse-error", "invalid", "future"]
                  },
                  "uniqueItems": true
                },
                "ignore_last_modified": { "type": "boolean" }
              }
            }
          }
        }
      }
    },
    "health": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "status",
        "status_since",
        "unknown_review",
        "last_checked_at",
        "message",
        "probe",
        "freshness",
        "integrity"
      ],
      "properties": {
        "status": {
          "enum": [
            "fresh",
            "aging",
            "stale",
            "degraded",
            "browser-dependent",
            "unreachable",
            "unknown-freshness",
            "unknown"
          ]
        },
        "status_since": { "$ref": "#/$defs/nullable_timestamp" },
        "unknown_review": {
          "type": "object",
          "additionalProperties": false,
          "required": ["unknown_since", "review_due_at", "review_required"],
          "properties": {
            "unknown_since": { "$ref": "#/$defs/nullable_timestamp" },
            "review_due_at": { "$ref": "#/$defs/nullable_timestamp" },
            "review_required": { "type": "boolean" }
          },
          "$comment": "All three values are null/null/false unless status is unknown. review_due_at is unknown_since + 30 days; review_required becomes true strictly after that instant. A successfully probed dataset may not remain unknown."
        },
        "last_checked_at": { "$ref": "#/$defs/nullable_timestamp" },
        "message": { "type": ["string", "null"] },
        "probe": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "request_url",
            "access_method",
            "access_dependency",
            "http_status",
            "content_length_bytes"
          ],
          "properties": {
            "request_url": { "type": ["string", "null"], "format": "uri" },
            "access_method": { "type": ["string", "null"] },
            "access_dependency": { "enum": ["direct", "browser", null] },
            "http_status": {
              "type": ["integer", "null"],
              "minimum": 100,
              "maximum": 599
            },
            "content_length_bytes": { "type": ["integer", "null"], "minimum": 0 }
          }
        },
        "freshness": {
          "type": "object",
          "additionalProperties": false,
          "required": ["candidates", "selected_signal", "age_seconds", "classification"],
          "properties": {
            "candidates": {
              "type": "object",
              "additionalProperties": false,
              "required": ["content_date", "last_modified_at", "last_checked_at"],
              "properties": {
                "content_date": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": ["field", "value", "parse_result", "reason"],
                  "properties": {
                    "field": { "type": ["string", "null"] },
                    "value": { "$ref": "#/$defs/nullable_date_or_timestamp" },
                    "parse_result": {
                      "enum": [
                        "success",
                        "not-configured",
                        "missing",
                        "parse-error",
                        "invalid",
                        "future"
                      ]
                    },
                    "reason": { "type": ["string", "null"] }
                  }
                },
                "last_modified_at": { "$ref": "#/$defs/nullable_timestamp" },
                "last_checked_at": { "$ref": "#/$defs/nullable_timestamp" }
              }
            },
            "selected_signal": {
              "type": "object",
              "additionalProperties": false,
              "required": ["kind", "value", "reason"],
              "properties": {
                "kind": {
                  "enum": ["content-date", "last-modified", "last-checked", "none"]
                },
                "value": { "$ref": "#/$defs/nullable_date_or_timestamp" },
                "reason": { "type": "string", "minLength": 1 }
              }
            },
            "age_seconds": { "type": ["integer", "null"], "minimum": 0 },
            "classification": {
              "enum": ["fresh", "aging", "stale", "unknown-freshness"]
            }
          }
        },
        "integrity": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "record_count",
            "record_count_is_estimated",
            "expected_record_count",
            "record_count_within_tolerance",
            "is_incomplete",
            "column_count",
            "shape_changed",
            "special_checks"
          ],
          "properties": {
            "record_count": { "type": ["integer", "null"], "minimum": 0 },
            "record_count_is_estimated": { "type": "boolean" },
            "expected_record_count": { "type": ["integer", "null"], "minimum": 0 },
            "record_count_within_tolerance": { "type": ["boolean", "null"] },
            "is_incomplete": { "type": "boolean" },
            "column_count": { "type": ["integer", "null"], "minimum": 0 },
            "shape_changed": { "type": ["boolean", "null"] },
            "special_checks": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["name", "status", "observed", "expected", "message"],
                "properties": {
                  "name": { "type": "string", "minLength": 1 },
                  "status": { "enum": ["pass", "fail", "not-run"] },
                  "observed": {},
                  "expected": {},
                  "message": { "type": ["string", "null"] }
                }
              }
            }
          }
        }
      }
    },
    "data_profile": {
      "type": "object",
      "additionalProperties": false,
      "required": ["date_range", "fields"],
      "properties": {
        "date_range": {
          "type": ["object", "null"],
          "additionalProperties": false,
          "required": ["start", "end"],
          "properties": {
            "start": { "type": ["string", "null"], "format": "date" },
            "end": { "type": ["string", "null"], "format": "date" }
          }
        },
        "fields": {
          "type": "array",
          "items": { "$ref": "#/$defs/field" }
        }
      }
    },
    "change_control": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "source_schema_version",
        "shape_fingerprint",
        "known_quirks",
        "breaking_changes"
      ],
      "properties": {
        "source_schema_version": { "type": ["string", "null"] },
        "shape_fingerprint": {
          "type": ["string", "null"],
          "pattern": "^sha256:[0-9a-f]{64}$"
        },
        "known_quirks": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 }
        },
        "breaking_changes": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 }
        }
      }
    },
    "links": {
      "type": "object",
      "additionalProperties": false,
      "required": ["self", "human_report", "catalog", "health_snapshot", "badge"],
      "properties": {
        "self": { "$ref": "#/$defs/canonical_dataset_url" },
        "human_report": {
          "type": "string",
          "pattern": "^https://data-pulse\\.my/data/[A-Za-z0-9_-]+\\.md$"
        },
        "catalog": {
          "const": "https://data-pulse.my/data/json/catalog.json"
        },
        "health_snapshot": {
          "const": "https://data-pulse.my/health/latest.json"
        },
        "badge": {
          "type": "string",
          "pattern": "^https://data-pulse\\.my/badges/[A-Za-z0-9_-]+\\.svg$"
        }
      }
    },
    "generation": {
      "type": "object",
      "additionalProperties": false,
      "required": ["generator", "generator_version", "cycle_checked_at", "inputs"],
      "properties": {
        "generator": { "const": "scripts/build_dataset_json.py" },
        "generator_version": { "type": "string", "minLength": 1 },
        "cycle_checked_at": { "$ref": "#/$defs/timestamp" },
        "inputs": {
          "type": "array",
          "minItems": 3,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["role", "path", "sha256"],
            "properties": {
              "role": {
                "enum": ["registry", "report-manifest", "probe-policy", "health-snapshot"]
              },
              "path": {
                "type": "string",
                "pattern": "^(datapulse\\.json|data/[A-Za-z0-9_-]+\\.md|[^/]+(?:/[^/]+)*/probe-policy\\.json|health/latest\\.json)$"
              },
              "sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" }
            }
          }
        }
      }
    }
  },
  "$defs": {
    "dataset_id": {
      "type": "string",
      "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$",
      "not": { "enum": ["schema", "context", "catalog"] }
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "pattern": "Z$"
    },
    "nullable_timestamp": {
      "oneOf": [
        { "$ref": "#/$defs/timestamp" },
        { "type": "null" }
      ]
    },
    "nullable_date_or_timestamp": {
      "oneOf": [
        { "type": "string", "format": "date" },
        { "$ref": "#/$defs/timestamp" },
        { "type": "null" }
      ]
    },
    "canonical_dataset_url": {
      "type": "string",
      "format": "uri",
      "pattern": "^https://data-pulse\\.my/data/json/[A-Za-z0-9_-]+\\.json$"
    },
    "field": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "type", "format", "unit", "description", "fields"],
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "type": { "type": "string", "minLength": 1 },
        "format": { "type": ["string", "null"] },
        "unit": { "type": ["string", "null"] },
        "description": { "type": ["string", "null"] },
        "fields": {
          "type": "array",
          "items": { "$ref": "#/$defs/field" }
        }
      }
    }
  },
  "allOf": [
    {
      "$comment": "Cross-field invariant: @id == canonical_url == links.self == https://data-pulse.my/data/json/{id}.json; report_url == links.human_report."
    },
    {
      "$comment": "Cross-field invariant: fixed-window thresholds equal baseline × 1.5 and × 3. For odd-second baselines, round upward to the next whole second."
    },
    {
      "$comment": "Cross-field invariant: survey-year uses last-checked only and ignore_last_modified=true. As-required ignores Last-Modified and defaults to unknown-freshness unless an explicitly configured publisher date_* field parses successfully."
    },
    {
      "$comment": "Cross-field invariant: status unknown is valid only before the first completed probe or during migration. After a completed probe, status must be one of the other seven values."
    }
  ]
}
```

### Freshness and status decision table

This table is normative for the proposed generator/classifier and makes G3–G5 executable.

| Cadence/mode | Selected freshness signal | Window | Result |
| --- | --- | --- | --- |
| Fixed-window with configured content field | Parse the configured field using its configured minimum/maximum selector. On missing, parse error, invalid value, or future value, fall back to valid `Last-Modified`. | `fresh` at age ≤ 1.5× baseline; `aging` at >1.5× and ≤3×; `stale` at >3×. | This is G3 hybrid content-first behavior. The output retains both candidates and the fallback reason. |
| Fixed-window without configured content field | Valid `Last-Modified`. | Same 1.5×/3× thresholds. Realtime and hourly use their actual cadence in seconds. | If the header is absent/invalid, `unknown-freshness`. |
| `survey-year` | Successful `last_checked_at`; ignore `Last-Modified`, even if present. | Use the slow-tier probe interval as the operational baseline: fresh ≤1.5×, aging ≤3×, stale >3×. | This reports whether the source has been authoritatively rechecked, not whether a new survey wave has been published. The distinction is included in `selected_signal.reason`. |
| `as-required` with no approved publisher `date_*` field | No signal; ignore `Last-Modified`. | No thresholds (`null`). | `unknown-freshness` by default. |
| `as-required` with an approved publisher `date_*` field | Parsed explicit publisher date only; ignore `Last-Modified`. | No inferred calendar SLA. | Successful evidence yields `fresh`; absent/invalid evidence yields `unknown-freshness`. `aging` and `stale` require a future explicitly approved publisher SLA, not an invented interval. |

Overall status precedence is deterministic: pre-probe `unknown`; then `browser-dependent` for a browser-required assessment; then `unreachable` for a failed/non-2xx direct request; then `degraded` for structural, completeness, or special-validation failure; then `stale`; `aging`; `unknown-freshness`; and finally `fresh`. This retains the current broad precedence while eliminating `healthy` and `current` synonyms. `status_since` is carried forward when the status is unchanged and reset to the cycle time when it changes. `unknown_since` is first set when an ID enters the registry without a completed probe; at 30 days `review_required` becomes true and repository verification should fail or emit a release-blocking review finding, depending on the enforcement mode.

## 5. Two example files

These are full illustrative outputs assembled from the live 2026-08-08 registry, reports, and observations. Timestamps, counts, sizes, hashes, and classifications are examples of generator-owned values, not constants or golden values to copy into implementation; input digests are shown as symbolic strings because the proposed normalized input files do not exist yet.

### `data/json/pharmaceutical_products.json`

This example demonstrates a monthly `pharmaceutical_*` identity and G3 fallback: `date_reg` is configured but rejected as administrative/future freshness evidence, so valid `Last-Modified` is selected.

```json
{
  "$schema": "https://data-pulse.my/data/json/schema.json",
  "schema_version": "datapulse/dataset/v1",
  "@context": "https://data-pulse.my/data/json/context.json",
  "@type": "Dataset",
  "@id": "https://data-pulse.my/data/json/pharmaceutical_products.json",
  "id": "pharmaceutical_products",
  "name": "Registered Pharmaceutical Products",
  "description": "Registered pharmaceutical products published by the National Pharmaceutical Regulatory Agency through data.gov.my.",
  "generated_at": "2026-08-08T05:49:42Z",
  "canonical_url": "https://data-pulse.my/data/json/pharmaceutical_products.json",
  "report_url": "https://data-pulse.my/data/pharmaceutical_products.md",
  "identity": {
    "id_namespace": "pharmaceutical",
    "portfolio_namespace": "healthcare",
    "scope": "Original CC BY 4.0 open-data pipeline dataset.",
    "related_datasets": [
      {
        "id": "npra_products_registered",
        "relation": "same-source-distinct-scope",
        "canonical_url": "https://data-pulse.my/data/json/npra_products_registered.json"
      }
    ]
  },
  "source": {
    "source_name": "data.gov.my",
    "steward": "National Pharmaceutical Regulatory Agency",
    "publisher": "National Pharmaceutical Regulatory Agency",
    "landing_page_url": null,
    "distributions": [
      {
        "role": "primary",
        "url": "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv",
        "media_type": "text/csv",
        "access_method": "direct"
      }
    ],
    "licence": {
      "name": "Creative Commons Attribution 4.0",
      "url": "https://creativecommons.org/licenses/by/4.0/"
    },
    "attribution": "National Pharmaceutical Regulatory Agency via data.gov.my",
    "geo_coverage": "Malaysia",
    "is_accessible_for_free": true
  },
  "publication": {
    "refresh_frequency": "monthly",
    "freshness_policy": {
      "cadence_class": "monthly",
      "mode": "fixed-window",
      "probe_interval_seconds": 604800,
      "baseline_seconds": 2592000,
      "thresholds": {
        "fresh_lte_seconds": 3888000,
        "aging_lte_seconds": 7776000,
        "stale_gt_seconds": 7776000
      },
      "signal_policy": {
        "content_date_field": "date_reg",
        "content_date_selector": "maximum",
        "precedence": ["content-date", "last-modified"],
        "fallback_on": ["missing", "parse-error", "invalid", "future"],
        "ignore_last_modified": false
      }
    }
  },
  "health": {
    "status": "fresh",
    "status_since": "2026-08-08T05:49:42Z",
    "unknown_review": {
      "unknown_since": null,
      "review_due_at": null,
      "review_required": false
    },
    "last_checked_at": "2026-08-08T05:49:42Z",
    "message": "HTTP 200",
    "probe": {
      "request_url": "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv",
      "access_method": "direct curl GET",
      "access_dependency": "direct",
      "http_status": 200,
      "content_length_bytes": 10552657
    },
    "freshness": {
      "candidates": {
        "content_date": {
          "field": "date_reg",
          "value": null,
          "parse_result": "future",
          "reason": "Future administrative registration dates are not accepted as publication freshness evidence."
        },
        "last_modified_at": "2026-08-06T22:31:03Z",
        "last_checked_at": "2026-08-08T05:49:42Z"
      },
      "selected_signal": {
        "kind": "last-modified",
        "value": "2026-08-06T22:31:03Z",
        "reason": "Configured content date was rejected; hybrid policy fell back to a valid Last-Modified header."
      },
      "age_seconds": 112719,
      "classification": "fresh"
    },
    "integrity": {
      "record_count": 28024,
      "record_count_is_estimated": false,
      "expected_record_count": 28024,
      "record_count_within_tolerance": true,
      "is_incomplete": false,
      "column_count": 16,
      "shape_changed": false,
      "special_checks": []
    }
  },
  "data_profile": {
    "date_range": null,
    "fields": [
      { "name": "reg_no", "type": "string", "format": null, "unit": null, "description": "Product registration number.", "fields": [] },
      { "name": "ref_no", "type": "string", "format": null, "unit": null, "description": "NPRA reference number.", "fields": [] },
      { "name": "product", "type": "string", "format": null, "unit": null, "description": "Registered product name.", "fields": [] },
      { "name": "status", "type": "string", "format": null, "unit": null, "description": "Registration status.", "fields": [] },
      { "name": "description", "type": "string", "format": null, "unit": null, "description": "Product description.", "fields": [] },
      { "name": "holder", "type": "string", "format": null, "unit": null, "description": "Registration holder.", "fields": [] },
      { "name": "holder_osa", "type": "string", "format": null, "unit": null, "description": "Holder address or associated source text.", "fields": [] },
      { "name": "manufacturer", "type": "string", "format": null, "unit": null, "description": "Manufacturer.", "fields": [] },
      { "name": "manufacturer_osa", "type": "string", "format": null, "unit": null, "description": "Manufacturer address or associated source text.", "fields": [] },
      { "name": "importer", "type": "string", "format": null, "unit": null, "description": "Importer.", "fields": [] },
      { "name": "importer_osa", "type": "string", "format": null, "unit": null, "description": "Importer address or associated source text.", "fields": [] },
      { "name": "date_reg", "type": "date", "format": "YYYY-MM-DD", "unit": null, "description": "Administrative registration date; not necessarily publication freshness.", "fields": [] },
      { "name": "date_end", "type": "date", "format": "YYYY-MM-DD", "unit": null, "description": "Administrative registration end date.", "fields": [] },
      { "name": "active_ingredient", "type": "string", "format": null, "unit": null, "description": "Active ingredient text.", "fields": [] },
      { "name": "mdc_code", "type": "string", "format": null, "unit": null, "description": "MDC classification code.", "fields": [] },
      { "name": "generic_name", "type": "string", "format": null, "unit": null, "description": "Generic product name.", "fields": [] }
    ]
  },
  "change_control": {
    "source_schema_version": "1.0",
    "shape_fingerprint": null,
    "known_quirks": [
      "Dates may represent future administrative events and must be validated before use as freshness evidence."
    ],
    "breaking_changes": []
  },
  "links": {
    "self": "https://data-pulse.my/data/json/pharmaceutical_products.json",
    "human_report": "https://data-pulse.my/data/pharmaceutical_products.md",
    "catalog": "https://data-pulse.my/data/json/catalog.json",
    "health_snapshot": "https://data-pulse.my/health/latest.json",
    "badge": "https://data-pulse.my/badges/pharmaceutical_products.svg"
  },
  "generation": {
    "generator": "scripts/build_dataset_json.py",
    "generator_version": "1",
    "cycle_checked_at": "2026-08-08T05:49:42Z",
    "inputs": [
      { "role": "registry", "path": "datapulse.json", "sha256": "<computed-at-generation>" },
      { "role": "report-manifest", "path": "data/pharmaceutical_products.md", "sha256": "<computed-at-generation>" },
      { "role": "probe-policy", "path": "config/probe-policy.json", "sha256": "<computed-at-generation>" },
      { "role": "health-snapshot", "path": "health/latest.json", "sha256": "<computed-at-generation>" }
    ]
  }
}
```

### `data/json/npra_products_registered.json`

This example demonstrates the preserved `npra_*` namespace. It intentionally shares an upstream CSV with the previous example but carries a distinct scope, cadence, validation check, identity, canonical URL, and report.

```json
{
  "$schema": "https://data-pulse.my/data/json/schema.json",
  "schema_version": "datapulse/dataset/v1",
  "@context": "https://data-pulse.my/data/json/context.json",
  "@type": "Dataset",
  "@id": "https://data-pulse.my/data/json/npra_products_registered.json",
  "id": "npra_products_registered",
  "name": "Verified Malaysian Pharmaceutical Registry",
  "description": "Agent-ready NPRA pharmaceutical registry manifest for paid-product provenance and registration-format verification.",
  "generated_at": "2026-08-08T06:00:59Z",
  "canonical_url": "https://data-pulse.my/data/json/npra_products_registered.json",
  "report_url": "https://data-pulse.my/data/npra_products_registered.md",
  "identity": {
    "id_namespace": "npra",
    "portfolio_namespace": "healthcare",
    "scope": "Paid-product provenance bundle with NPRA-specific registration-format validation.",
    "related_datasets": [
      {
        "id": "pharmaceutical_products",
        "relation": "same-source-distinct-scope",
        "canonical_url": "https://data-pulse.my/data/json/pharmaceutical_products.json"
      }
    ]
  },
  "source": {
    "source_name": "NPRA via data.gov.my",
    "steward": "National Pharmaceutical Regulatory Agency",
    "publisher": "National Pharmaceutical Regulatory Agency, Ministry of Health Malaysia",
    "landing_page_url": "https://www.npra.gov.my/index.php/my/consumers-2/maklumat/carian-produk-berdaftar-bernotifikasi.html",
    "distributions": [
      {
        "role": "landing-page",
        "url": "https://quest3plus.bpfk.gov.my/pmo2/index.php",
        "media_type": "text/html",
        "access_method": "browser"
      },
      {
        "role": "primary",
        "url": "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv",
        "media_type": "text/csv",
        "access_method": "direct"
      }
    ],
    "licence": {
      "name": "Creative Commons Attribution 4.0",
      "url": "https://creativecommons.org/licenses/by/4.0/"
    },
    "attribution": "National Pharmaceutical Regulatory Agency, Ministry of Health Malaysia via data.gov.my",
    "geo_coverage": "Malaysia",
    "is_accessible_for_free": true
  },
  "publication": {
    "refresh_frequency": "daily",
    "freshness_policy": {
      "cadence_class": "daily",
      "mode": "fixed-window",
      "probe_interval_seconds": 86400,
      "baseline_seconds": 86400,
      "thresholds": {
        "fresh_lte_seconds": 129600,
        "aging_lte_seconds": 259200,
        "stale_gt_seconds": 259200
      },
      "signal_policy": {
        "content_date_field": "date_reg",
        "content_date_selector": "maximum",
        "precedence": ["content-date", "last-modified"],
        "fallback_on": ["missing", "parse-error", "invalid", "future"],
        "ignore_last_modified": false
      }
    }
  },
  "health": {
    "status": "fresh",
    "status_since": "2026-08-08T06:00:59Z",
    "unknown_review": {
      "unknown_since": null,
      "review_due_at": null,
      "review_required": false
    },
    "last_checked_at": "2026-08-08T06:00:59Z",
    "message": "HTTP 200; registration format compatible",
    "probe": {
      "request_url": "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv",
      "access_method": "direct curl GET with NPRA registration validation",
      "access_dependency": "direct",
      "http_status": 200,
      "content_length_bytes": 10552657
    },
    "freshness": {
      "candidates": {
        "content_date": {
          "field": "date_reg",
          "value": null,
          "parse_result": "future",
          "reason": "Future administrative date_reg values are not accepted as publication freshness evidence."
        },
        "last_modified_at": "2026-08-06T22:31:03Z",
        "last_checked_at": "2026-08-08T06:00:59Z"
      },
      "selected_signal": {
        "kind": "last-modified",
        "value": "2026-08-06T22:31:03Z",
        "reason": "Configured content date was rejected; hybrid policy fell back to a valid Last-Modified header."
      },
      "age_seconds": 113396,
      "classification": "fresh"
    },
    "integrity": {
      "record_count": 28024,
      "record_count_is_estimated": false,
      "expected_record_count": 28024,
      "record_count_within_tolerance": true,
      "is_incomplete": false,
      "column_count": 16,
      "shape_changed": false,
      "special_checks": [
        {
          "name": "npra-registration-format-compatible",
          "status": "pass",
          "observed": {
            "accepted_formats": ["legacy-compact", "transition"]
          },
          "expected": {
            "invalid_registration_count": 0
          },
          "message": "Registration values are case-normalized and checked against both approved transition-window formats."
        }
      ]
    }
  },
  "data_profile": {
    "date_range": null,
    "fields": [
      { "name": "reg_no", "type": "string", "format": "NPRA registration number", "unit": null, "description": "Legacy compact or transition-format MAL registration value.", "fields": [] },
      { "name": "ref_no", "type": "string", "format": null, "unit": null, "description": "NPRA reference number.", "fields": [] },
      { "name": "product", "type": "string", "format": null, "unit": null, "description": "Registered product name.", "fields": [] },
      { "name": "status", "type": "string", "format": null, "unit": null, "description": "Registration status.", "fields": [] },
      { "name": "description", "type": "string", "format": null, "unit": null, "description": "Product description.", "fields": [] },
      { "name": "holder", "type": "string", "format": null, "unit": null, "description": "Registration holder.", "fields": [] },
      { "name": "holder_osa", "type": "string", "format": null, "unit": null, "description": "Holder address or associated source text.", "fields": [] },
      { "name": "manufacturer", "type": "string", "format": null, "unit": null, "description": "Manufacturer.", "fields": [] },
      { "name": "manufacturer_osa", "type": "string", "format": null, "unit": null, "description": "Manufacturer address or associated source text.", "fields": [] },
      { "name": "importer", "type": "string", "format": null, "unit": null, "description": "Importer.", "fields": [] },
      { "name": "importer_osa", "type": "string", "format": null, "unit": null, "description": "Importer address or associated source text.", "fields": [] },
      { "name": "date_reg", "type": "date", "format": "YYYY-MM-DD", "unit": null, "description": "Administrative registration date; not a reliable publication-freshness signal when future-dated.", "fields": [] },
      { "name": "date_end", "type": "date", "format": "YYYY-MM-DD", "unit": null, "description": "Administrative registration end date.", "fields": [] },
      { "name": "active_ingredient", "type": "string", "format": null, "unit": null, "description": "Active ingredient text.", "fields": [] },
      { "name": "mdc_code", "type": "string", "format": null, "unit": null, "description": "MDC classification code.", "fields": [] },
      { "name": "generic_name", "type": "string", "format": null, "unit": null, "description": "Generic product name.", "fields": [] }
    ]
  },
  "change_control": {
    "source_schema_version": "1.0",
    "shape_fingerprint": null,
    "known_quirks": [
      "QUEST3+ returns HTTP 400 to curl's default user agent; a browser-like user agent returns HTTP 200.",
      "date_reg and date_end may contain future administrative dates and are not reliable publication-freshness signals.",
      "Registration values are case-normalized before old/new transition-format validation."
    ],
    "breaking_changes": [
      "From 2026-08-10, accept MAL + 8-digit Registration Number + Product Classification while retaining legacy-format support during the transition window."
    ]
  },
  "links": {
    "self": "https://data-pulse.my/data/json/npra_products_registered.json",
    "human_report": "https://data-pulse.my/data/npra_products_registered.md",
    "catalog": "https://data-pulse.my/data/json/catalog.json",
    "health_snapshot": "https://data-pulse.my/health/latest.json",
    "badge": "https://data-pulse.my/badges/npra_products_registered.svg"
  },
  "generation": {
    "generator": "scripts/build_dataset_json.py",
    "generator_version": "1",
    "cycle_checked_at": "2026-08-08T06:00:59Z",
    "inputs": [
      { "role": "registry", "path": "datapulse.json", "sha256": "<computed-at-generation>" },
      { "role": "report-manifest", "path": "data/npra_products_registered.md", "sha256": "<computed-at-generation>" },
      { "role": "probe-policy", "path": "config/probe-policy.json", "sha256": "<computed-at-generation>" },
      { "role": "health-snapshot", "path": "health/latest.json", "sha256": "<computed-at-generation>" }
    ]
  }
}
```

The literal `<computed-at-generation>` digest markers make these examples explanatory rather than schema-valid fixtures. A generated file must contain lowercase 64-character SHA-256 values.

## 6. Generator changes required

### Generation flow

```text
datapulse.json + normalized data/<id>.md front matter + probe-policy.json
                              |
                              v
scripts/check.sh adapters -> normalized probe JSONL
                              |
                              v
pure scheduler/classifier (PLAN A2)
  - select content-first/fallback signal
  - apply cadence-specific thresholds
  - apply status precedence and unknown review rule
  - merge due rows with previous snapshot
                              |
                              v
health/latest.json (atomic cycle snapshot)
                              |
                              v
scripts/generate.py health-cycle (PLAN A4 orchestrator)
  1. gen_data_reports.sh
  2. build_dataset_json.py
  3. gen_badges.sh / gen_rss.sh / summaries / changelog
  4. repository-contract verification
                              |
                              v
data/json/<id>.json + data/json/catalog.json + all other generated views
```

### `scripts/check.sh`

Keep transport and adapter dispatch here, but stop embedding final scheduling, signal selection, and classification in its large `jq` program. It should emit normalized probe rows with raw candidates and parse outcomes, including both the raw/validated content date and `Last-Modified`; the classifier must be able to explain why fallback occurred. In particular, replace the associative `DATASET_CONTENT_DATE_FIELDS`, rolling selector, browser settings, and special-validation switches with reads from the validated probe-policy document described by PLAN A1.

The normalized probe contract needs at least:

```json
{
  "dataset_id": "<id>",
  "probed_at": "<RFC3339 UTC timestamp>",
  "request": {
    "url": "<resolved URL>",
    "access_method": "<adapter>",
    "http_status": 200,
    "content_length_bytes": 123
  },
  "freshness_candidates": {
    "content_date": {
      "field": "<configured field or null>",
      "selector": "maximum",
      "raw_value": "<raw value or null>",
      "normalized_value": "<date or null>",
      "parse_result": "success|not-configured|missing|parse-error|invalid|future",
      "reason": "<machine-generated explanation>"
    },
    "last_modified_at": "<RFC3339 timestamp or null>"
  },
  "measurements": {
    "record_count": 123,
    "record_count_is_estimated": false,
    "column_count": 4,
    "date_range": { "start": "<date>", "end": "<date>" },
    "shape_fingerprint": "sha256:<digest>"
  },
  "special_checks": []
}
```

No value in this probe envelope is classified as `fresh`, `aging`, or `stale`; it is evidence for the single classifier.

### `scripts/extract_content_freshness.sh`

Change it from a mostly global date scraper plus a `met_weather` case into a policy-driven extractor. It should receive the configured field, selector (`minimum`, `maximum`, or `publisher-explicit`), and validation rules, and return a structured result rather than an empty string on every failure. This preserves the fixed DOSM hybrid behavior from G3: only a successful, valid content parse wins; all approved failure states remain visible so `Last-Modified` fallback is testable. It must not scan unrelated date-like text when a field is configured, because registration and expiry dates can otherwise masquerade as publication dates.

### New pure scheduler/classifier module

Implement PLAN A2 as a Python module and narrow CLI used by `check.sh`. It owns:

1. manifest cadence normalization and due selection;
2. G3 signal precedence and fallback reasons;
3. G4 fixed, survey-year, and as-required rules;
4. overall status precedence;
5. `status_since`, `unknown_since`, and the G5 30-day review calculation;
6. due-mode merge in manifest order; and
7. `_trust_summary` generation.

Fixture tests must cover every supported manifest frequency, both exact boundaries (1.5× and 3×), content success and each fallback cause, realtime/hourly seconds, survey-year header suppression, as-required with and without an explicit date, all eight status triggers, first probe removal of `unknown`, and the 30-day review boundary.

### New `scripts/build_dataset_json.py`

This should be the only writer of `data/json/schema.json`, `context.json`, `catalog.json`, and every `data/json/<id>.json`. It should:

1. validate `datapulse.json`, normalized report front matter, probe policy, and `health/latest.json` before merging;
2. require exact ID-set equality among registry, reports selected for publication, health rows, canonical JSON output, JSON-LD catalog membership, and dataset badges;
3. reject orphan output files and reserved IDs;
4. calculate all DataPulse-owned URLs from the single constant `https://data-pulse.my`;
5. preserve official upstream URLs without rewriting them;
6. emit the stable schema above with explicit nulls and deterministic ordering;
7. calculate input SHA-256 digests and a normalized structural fingerprint;
8. write into a temporary directory, validate every document against `schema.json`, and atomically replace the generated set only after the full set passes; and
9. generate a compact `catalog.json` whose dataset entries link to `data/json/<id>.json` and whose JSON-LD `@id` and `url` use `https://data-pulse.my/data/json/catalog.json`.

The generator may read `health/latest.json` rather than raw probe JSONL because the classifier has already made the authoritative decision. It must never reclassify status independently.

### `scripts/gen_jsonld_catalog.py`

Retire this as a separate per-dataset generator after its useful schema.org projection is absorbed into `build_dataset_json.py` and `context.json`. During migration it can become a thin compatibility wrapper that invokes the new generator, but it must not write `data/jsonld/` or maintain a second status calculation.

### `scripts/gen_data_reports.sh`

Keep it as the Markdown view generator, but run it on every successful timer cycle under G6. It should consume exactly the same health row as `build_dataset_json.py`; report front matter must not become a second computed-health authority. Separate hand-authored front matter from generated observation fields, or have the generator preserve only an explicit allowlist of editorial fields.

### Generation orchestrator and workflows

Add the PLAN A4 generation orchestrator with a `health-cycle` profile. Both the 15-minute systemd service and the weekly GitHub Actions fallback should call this same profile after producing `health/latest.json`; the current weekly workflow does not call `gen_data_reports.sh` or regenerate JSON-LD, and the current Pages workflow regenerates JSON-LD separately. The health-cycle commit scope should include at least `health/`, `data/*.md` generated sections, `data/json/`, `badges/`, `feed.xml`, `README.md`, and `changelog.json`. Pages should package already-verified artifacts rather than becoming the only place that refreshes one representation.

### Repository-contract verifier

Extend the proposed PLAN A4 verifier so CI fails when:

- any registry ID lacks exactly one report, canonical JSON file, catalog entry, health row, or dataset badge;
- an unregistered `npra_*` report remains outside the canonical ID set;
- a `pharmaceutical_*` or `npra_*` identity is silently aliased to the other namespace;
- a canonical document fails schema or cross-field validation;
- generated DataPulse-owned URLs use the GitHub Pages origin or another host;
- `generated_at`/`generation.cycle_checked_at` does not match the health cycle being packaged;
- an output digest does not match its input;
- `unknown` survives a completed first probe or exceeds 30 days without a review finding; or
- a stale/orphan file remains under `data/json/` or `data/jsonld/`.

## 7. Migration path from current state

1. **Freeze and inventory the current surfaces.** Generate an ID compatibility table from the live registry, reports, `data/json/`, `data/jsonld/`, health, and badges. Save the 92 legacy JSON envelopes as migration fixtures; do not make them generator inputs after migration.
2. **Normalize hand-authored inputs.** Define a front-matter schema and update all reports to carry `id`, title/description, scope, structured fields, quirks, changes, attribution, and any alternate source links. One-time migration may extract the useful `fields`, `checks`, and reproducibility facts from legacy JSON and Markdown tables, followed by human review.
3. **Preserve G1 in the registry.** Add `npra_products_registered`, `npra_cosmetic_notifications`, and `npra_drug_registration_guidance` to `datapulse.json` as first-class rows with their own cadence, scope, licensing, probe policy, report, and expected measurements. Keep all existing `pharmaceutical_*` rows and IDs. Declare only `same-source-distinct-scope` relationships where appropriate.
4. **Land policy and classification first.** Add the validated probe-policy input, pure classifier, fixtures, and compatibility comparison. Update `health/latest.json` so every registry ID receives a row and so post-probe `unknown` is impossible.
5. **Land the canonical generator additively.** Initially generate the complete new `data/json/` set, `schema.json`, `context.json`, and `catalog.json` while the legacy JSON-LD paths still exist. Validate ID equality and compare the new schema.org projection with the old catalog.
6. **Replace heterogeneous files in place.** Overwrite all 92 legacy `data/json/<id>.json` files with v1 canonical documents and create the missing files for every remaining registry ID. Nothing is moved from `data/json/`; the path is retained while its contract is versioned and normalized.
7. **Move catalog ownership.** Replace `data/jsonld/catalog.json` with `data/json/catalog.json`, update dashboard embedding, MCP references, README links, release invariants, Pages smoke tests, and agent discovery to the new URL. All new generated links use `https://data-pulse.my`.
8. **Retire the duplicate directory.** After the compatibility policy in Open Question 1 is resolved, delete all per-dataset `data/jsonld/<id>.json` files and `data/jsonld/catalog.json`, then remove the empty directory and the old generator. If redirects are approved, implement them at the hosting layer; do not retain duplicate JSON bodies as redirects-in-name-only.
9. **Unify every cycle.** Change systemd and weekly fallback execution to probe, atomically write health, run the `health-cycle` generation profile, verify the repository contract, and only then commit/publish. A failed derived generation must leave the previous complete generated set intact and fail the cycle rather than publishing mixed timestamps.

### Keep, move, regenerate, delete

| Current artifact | Action | Target/justification |
| --- | --- | --- |
| `datapulse.json` | Keep and expand | Remains public registry/scheduling source; add preserved `npra_*` identities. |
| `data/<id>.md` | Keep and normalize | Remains human/editorial source plus generated report view. |
| Existing `data/json/<id>.json` | Regenerate in place | Same canonical path, one v1 schema, complete ID coverage. |
| `data/jsonld/<id>.json` | Delete after compatibility window | Its JSON-LD semantics move into canonical `<id>.json`. |
| `data/jsonld/catalog.json` | Move contract, regenerate at new path | Becomes `data/json/catalog.json`. |
| `health/latest.json` | Keep | Atomic portfolio snapshot and generator input, not an alternate per-ID contract. |
| `badges/` | Keep and regenerate every cycle | Presentation derived from the same classified health rows. |
| `scripts/gen_jsonld_catalog.py` | Retire or temporary wrapper | New canonical generator owns JSON and JSON-LD together. |
| Legacy JSON-only curated facts | Migrate once into normalized report front matter | Prevents generated output from becoming its own source. |

## 8. Open questions

**Status:** All five resolved by Redza on 2026-08-08.

1. **Legacy JSON-LD URL compatibility:** **B — Document the break, no redirects.** `https://data-pulse.my/data/jsonld/<id>.json` and `/catalog.json` URLs will return 410 Gone (or 404 with explanation) once the canonical workspace ships. Reasoning: redirects add hosting-layer complexity, double the per-request work for any consumer that doesn't update, and obscure the canonical-path change behind cosmetic URL preservation. The migration is announced in the changelog + README + `llms.txt`. Consumers that need the data should update to the new path. Acceptable for a trust-layer product where canonical paths are part of the value proposition.
2. **Survey-year operational window:** **A — Verification overdue.** For `survey-year` cadence, `aging` and `stale` describe "we haven't re-verified the source is still live" rather than "the data is old." Slow-tier probe interval is 30 days (matches the current behaviour). A survey-year dataset that hasn't been re-verified in 90 days is `stale`; that means "we don't know if a new edition has been published," not "the data is 3 years out of date." Apply the same 1.5×/3× cadence windows (45d aging, 90d stale) for verification.
3. **As-required explicit dates:** **A — Free tier: no manual SLAs.** Datasets with `as-required` cadence stay at `unknown-freshness` until a publisher-emitted `date_*` field appears in the source. No manually approved publisher SLAs on the free tier. This keeps the public taxonomy clean: a dataset is either "fresh because the source has a date" or "we don't know when next publication is." Manual SLAs are a paid-tier feature for later (e.g. "we'll notify you within 24h of any new release we observe"). For now: free tier enforces one rule; paid tier can be more lenient once the product is shaped.
4. **Canonical registry total after G1:** **A — Keep all 3 `npra_*` manifests private.** All three (`npra_products_registered`, `npra_cosmetic_notifications`, `npra_drug_registration_guidance`) are explicitly framed as "Paid-product raw manifest" in their notes. They stay in `data/` for documentation, but **do not** enter the public registry (`datapulse.json` stays at 166 IDs for now). They are engine-side provenance artifacts, not datapulse-my public surfaces. The public registry continues to describe publicly-distributable datasets; the engine handles the NPRA-provenance bundle internally. If a future decision moves any of these to public, that is a separate G8-style decision with its own migration.
5. **Descriptions and field semantics:** **A — Front matter as the sole structured source.** YAML front matter in `data/<id>.md` remains the canonical hand-authored input for license, attribution, known quirks, breaking changes, etc. The front matter pattern is already the convention; introducing a separate metadata file would double the per-dataset file count and create a sync risk. For datasets where front matter becomes too crowded (some manifests already have 30+ lines), opt-in to a dedicated `data/<id>.meta.yaml` file **for that specific dataset only** — this is an exception, not a general pattern. Default: front matter only.
