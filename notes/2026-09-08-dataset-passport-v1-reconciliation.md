# Dataset Passport v1 reconciliation

Passport v1 projects the current canonical manifest and health snapshot into one deterministic object per canonical dataset ID. It deliberately does not use `data/*.md` as the population: that directory contains three NPRA documentation artefacts beyond the 418 manifest datasets.

`data/passports/` is a distinct generated surface from the legacy `data/json/` envelopes. Missing legacy envelopes, source digests, record evidence, transformation lineage, witness references, and privacy classifications are represented as explicit unavailable evidence. The pharmaceutical-products record-evidence pilot is the only enabled record-level reference.

Catalogue graph edges are exposed only as literal `catalogue_relationships`; they do not assert transformation lineage. The Passport repeats the existing six-dimension quality profile unchanged and makes no semantic quality, completeness, truth, legal, safety, certification, or AI-admission claim.
