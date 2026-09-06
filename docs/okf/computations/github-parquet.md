---
type: "Attested Computation"
title: "DataPulse probe family: github_parquet"
description: "Deterministic DataPulse health probe receipt projection for the github_parquet family."
status: "stable"
runtime: "datapulse-pipeline"
parameters:
  - {"name": "dataset_id","type": "string","required": true}
executor: {"resource": "scripts/gen_per_dataset_receipt.py","receipt": ["dataset_id","last_checked","http_status","content_freshness_date","record_count"]}
attester: {"resource": "docs/datapulse-intro.md#verify-one-dataset"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-06T17:16:08Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-06T17:16:08Z"}
---

# Computation

Run the recorded DataPulse probe pipeline for the supplied `dataset_id` and inspect the declared receipt fields.
