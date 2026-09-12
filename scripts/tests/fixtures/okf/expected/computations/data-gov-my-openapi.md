---
type: "Attested Computation"
title: "DataPulse probe family: data_gov_my_openapi"
description: "Deterministic DataPulse health probe receipt projection for the data_gov_my_openapi family."
status: "stable"
runtime: "datapulse-pipeline"
parameters:
  - {"name": "dataset_id","type": "string","required": true}
executor: {"resource": "scripts/gen_per_dataset_receipt.py","receipt": ["dataset_id","last_checked","http_status","content_freshness_date","record_count"]}
attester: {"resource": "scripts/verify_per_dataset_receipt.py"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-01T12:00:00Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-01T12:00:00Z"}
---

# Computation

Run the recorded DataPulse probe pipeline for the supplied `dataset_id` and inspect the declared receipt fields.
