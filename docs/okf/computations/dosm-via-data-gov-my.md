---
type: "Attested Computation"
title: "DataPulse probe family: dosm_via_data_gov_my"
description: "Deterministic DataPulse health probe receipt projection for the dosm_via_data_gov_my family. This date governs the probe method, not data freshness; per-dataset freshness signals live on the Dataset concepts."
status: "stable"
runtime: "datapulse-pipeline"
parameters:
  - {"name": "dataset_id","type": "string","required": true}
executor: {"resource": "scripts/gen_per_dataset_receipt.py","receipt": ["dataset_id","last_checked","http_status","content_freshness_date","record_count"]}
attester: {"resource": "scripts/verify_per_dataset_receipt.py"}
sources:
  - {"id": "receipt-generator","resource": "scripts/gen_per_dataset_receipt.py","title": "Per-dataset receipt generator","digest": "sha256:9fc4c67332ee0e5c92f4c7450d7d3f3ffbad7c5030a9aec3b4c2ddb6f360687a"}
  - {"id": "receipt-verifier","resource": "scripts/verify_per_dataset_receipt.py","title": "Per-dataset receipt verifier (attester)","digest": "sha256:c63435dc0b85117b206c740ecdf63da034fea97e312bbe1d46d30cd59b206d38"}
  - {"id": "bundle-signer","resource": "scripts/gen_sigstore_bundle.py","title": "Sigstore bundle statement helpers","digest": "sha256:e806cf9b46662cf34a927424825936ee319da7045c1aff7cf67ddee59d3bf50c"}
generated: {"by": "process:datapulse-pipeline","at": "2026-09-12T02:03:02Z"}
verified:
  - {"by": "process:datapulse-health-timer","at": "2026-09-12T02:03:02Z"}
stale_after: "2026-12-11T02:03:02Z"
---

# Computation

Run the recorded DataPulse probe pipeline for the supplied `dataset_id` and inspect the declared receipt fields. Hash the bytes of each declared `sources` path with sha256 and compare against its recorded `digest`; a mismatch means the recipe moved since this bundle was generated.
