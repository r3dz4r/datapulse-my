# The "product description" layer: which named artifacts a buyer or auditor actually expects

All URLs retrieved **2026-09-26**. Reference numbers key to the source list at the end.

## 1. The distinction that governs every recommendation below

Two different document types are routinely conflated:

- **Publisher-side documentation** — the owner of the data describes *its own* dataset: Datasheets for Datasets, Data Statements, Croissant, FAIR, DCAT/DCAT-AP records, DataCite metadata. These describe motivation, composition, collection, schema, licence, provenance.
- **Verifier-side documentation** — a third party asserts *observations about someone else's* data: freshness, drift, reachability, record counts, attestations. The formal opening for this exists in W3C's Data Quality Vocabulary, which explicitly rejects a single definition of quality and states that "Certification agencies, data aggregators, data consumers can make relevant quality assessments, too" and that publishers "should not be the only ones to have a say on the quality of data" [9]. DCAT and DQV are both designed to let a non-publisher publish metadata *about* a dataset it does not own [5][9].

A trust layer that ships a Datasheet or Croissant file for data it does not own is mis-describing the artifact. It should ship DCAT/schema.org *descriptions*, DQV-style *quality assertions*, and its own *contract* — not a publisher's datasheet.

## 2. The standards, and what each one actually produces

| # | Standard | Artifact produced | Audience | Machine-readable? | Adoption evidence (who ships it) | Maintenance cost |
|---|---|---|---|---|---|---|
| 1 | Datasheets for Datasets (Gebru et al.) | Prose questionnaire (motivation, composition, collection, preprocessing, uses, distribution, maintenance) shipped with a dataset | Dataset creators + consumers; policy, journalists | No — narrative document; no schema, no validator [1] | Academic adopters and internal pilots at Microsoft, Google, IBM, per the paper's own impact section; recommended practice, not enforced [1] | High per dataset (human writing, revised as the dataset changes) |
| 2 | Data Statements (Bender & Friedman) | Long + short prose form for NLP/language datasets; schema now at Version 3 | NLP researchers, language-technology teams, data-subject communities | No — prose; schema is a list of elements, not a schema file [2][3] | UW Tech Policy Lab maintains schema v1→v3 across 2018–2024 publications [3] | High per dataset; community-run guidance, no tooling mandate |
| 3 | Croissant (MLCommons) | JSON-LD file (schema.org/Dataset + `cr:` terms: FileObject/FileSet/RecordSet/Field, plus RAI extension) | ML dataset publishers, ML tooling, dataset search, AI agents | Yes — versioned JSON-LD with `dct:conformsTo http://mlcommons.org/croissant/1.0` / `1.1`, plus a Python library and validator [4][5] | Kaggle (export button + download URL), Hugging Face (embedded JSON-LD + `/croissant` API), OpenML, Harvard Dataverse, Google Dataset Search Croissant filter; the NeurIPS 2024 paper reports 400,000+ datasets across the three repositories [5][6][7] | Medium–high: per-field schema, extraction and transforms; inferable from existing metadata in the HF/Kaggle case [6] |
| 4 | Frictionless Data Package / Data Resource (now "Data Package Standard") | `datapackage.json` descriptor (resources, schema, licences, sources) + resource descriptors | Data curators, portal operators, analysts | Yes — JSON with published profiles; Python/R/JS tooling [8] | Zenodo export endpoint per record; CKAN extension exposing `/dataset/<id>/datapackage.json`; Open Data Editor [8][10] | Low–medium if generated from existing metadata; higher if hand-curated table schemas |
| 5 | DCAT 3 (W3C Recommendation, 22 Aug 2024) | RDF vocabulary: Catalogue, Dataset, Distribution, DataService, DatasetSeries; Turtle/RDF-XML/JSON-LD | Data portal operators, aggregators, national catalogs | Yes — RDF, W3C Rec with implementation report [5] | Underpins DCAT-AP and every major European portal [5][11] | Low per record once catalogued; needs an RDF pipeline |
| 6 | DCAT-AP 3.0.x (SEMIC, Interoperable Europe) + HVD annex | Application profile of DCAT for European portals: mandatory/recommended properties per class, controlled vocabularies | EU public-sector publishers, national portals, harvesters | Yes — RDF/JSON-LD; conformance is machine-checkable (MQA) [11][12] | data.europa.eu harvests 170+ catalogues / ~1.4M datasets and runs Metadata Quality Assurance scoring DCAT-AP compliance, machine-readable formats and licence use [12][13]; Implementing Regulation (EU) 2023/138 requires HVD metadata in machine-readable form and HVD denotation, with DCAT-AP-HVD as the guidance profile [14][15] | Medium: vocabulary versioning (DCAT 2→3 migrations), controlled vocabularies, licence normalisation |
| 7 | schema.org/Dataset (+ DataCatalog, DataDownload) | JSON-LD / RDFa / microdata annotated web pages | Search engines, web-scale discovery, AI crawlers | Yes — JSON-LD, but loose: properties are optional, no required validator [16] | schema.org reports usage on 10K–100K domains (Google web index, July 2026); Google Dataset Search consumes it and offers a Croissant filter [16][7] | Low: extend existing pages; the cost is keeping it consistent with the source of truth |
| 8 | W3C Data on the Web Best Practices (Rec, 31 Jan 2017) | 35 numbered best practices across metadata, licences, provenance, quality, versioning, identifiers, formats, vocabularies, access, preservation, feedback, enrichment, republication | Data publishers and portal operators | Partly — normative prose, but it *mandates* machine-readable artifacts: "Provide data licence information", "Provide data provenance information", "Provide data quality information", "Provide a version indicator", "Use persistent URIs as identifiers of datasets" [17] | W3C Recommendation with an implementation report; the checklist function is its main adoption [17] | One-off design cost, then low — a checklist, not a per-dataset artifact |
| 9 | W3C Data Quality Vocabulary (DQV, WG Note 15 Dec 2016) | RDF: `dqv:Dimension`, `dqv:Metric`, `dqv:QualityMeasurement`, `dqv:QualityPolicy`, `dqv:QualityMetadata`; annotations by publishers *or* third parties | Anyone assessing fitness for purpose: aggregators, certifiers, consumers | Yes — RDF vocabulary intended as a DCAT extension [9] | W3C Working Group Note, not a Recommendation; implementations are tracked on a wiki page rather than a mandatory profile [9] | Low–medium: attach measurements to existing pipeline outputs; the vocabulary is small |
| 10 | Open Data Contract Standard (ODCS, Bitol / LF AI & Data) | YAML data contract: fundamentals, schema, references, data quality, support channels, pricing, team, roles, SLA, infrastructure — media type `application/odcs+yaml;version=3.x` | Data producers and their consumers; platform/governance engineers | Yes — YAML with companion JSON Schema for IDE validation [18] | Lineage from PayPal's Data Contract Template to Bitol (LF AI & Data sandbox project, Nov 2023); repo shows ~1.1k stars and named corporate contributors [18][19][20] | Medium: contract must be versioned with the interface; quality/SLA clauses need real enforcement |
| 11 | Open Data Product Specification (ODPS 4.1, Linux Foundation, released 24 Oct 2025) | YAML/JSON data-product descriptor: product details, strategy, contract, SLA (11 dimensions), data quality (8 options), pricing (12 models), licensing, access | Data product owners, marketplaces, enterprise governance | Yes — YAML + JSON Schema, Apache-2.0 [21] | Weak: Apache-2.0 spec under Linux Foundation with named maintainers, but the v4.1 repository shows single-digit stars; no primary evidence of large-scale production deployment found [21][22] | Medium: another manifest to keep in sync with the product |
| 12 | Data mesh "data as a product" (Dehghani) | Not a document — architectural vocabulary. A data product is the node encapsulating code, data+metadata (including quality metrics and semantic/syntactic schema), and infrastructure; it must be discoverable, addressable, trustworthy, self-describing, interoperable, secure | Enterprise data platform teams | N/A — implies machine-readable metadata, prescribes no format [23][24] | Widely cited (Martin Fowler, Thoughtworks, IBM glossaries); source of most "data product" wording [23][24][25] | N/A — framing, not an artifact to maintain |
| 13 | DataCite Metadata Schema (v4.7, released 3 Mar 2026) | Metadata record for a DOI (XML/JSON): Table 1 mandatory = Identifier, Creator, Title, Publisher, PublicationYear, ResourceType; then recommended/optional properties incl. RelatedIdentifier, Rights, Version, GeoLocation | Research data repositories, librarians, citation indexers | Yes — schema with obligation levels, REST API, public data files [26][27] | 100M+ DOIs registered, 1,667+ member organisations, ~3,900 repositories; 2025 public data file covers 108M findable DOIs [28][29] | Medium: registering and maintaining DOIs needs repository infrastructure; a citation block alone is cheap |
| 14 | FAIR principles (Wilkinson et al. 2016) | No single artifact; 15 guiding principles (F1–F4, A1–A2, I1–I3, R1.1–R1.3) that metadata/data must satisfy, including "a clear and accessible data usage license", "detailed provenance", and "domain-relevant community standards" | Research data community, funders, repositories | Principles are prose; machine-checkable only via metric tooling (e.g. F-UJI, FAIRsFAIR metrics) [30][31] | Near-universal as policy language; F-UJI gives automated dataset-level assessment [30][31] | Low to *claim*, high to *demonstrate* — needs reproducible metric outputs |
| 15 | "Dataset passport" / data-quality report conventions | No adopted cross-industry standard by that name. What exists: (a) DQV quality annotations [9]; (b) portal-level metadata quality reports, e.g. data.europa.eu's MQA dashboards and downloadable reports [12][13]; (c) research prototypes such as the AI Model Passport / AIPassport and imaging "dataset passport" reporting structures — proposals, not standards [32][33] | Portal operators, research auditors, MLOps | Bespoke per implementation; DCAT/DQV-shaped where mature [9][32] | No primary adoption source found for a standardised "dataset passport"; treat any such claim as vendor- or project-specific | Low if it projects data you already publish; high if it needs new manual attestation |
| 16 | DAMA data-quality dimensions (DMBOK 2nd ed. + revision) | Not an artifact — a controlled list of dimensions. DMBOK2 Table 29 lists 8 (accuracy, completeness, consistency, integrity, reasonability, timeliness, uniqueness, validity); the revision adds currency (9) and refines definitions with examples. DAMA UK's separate white paper defines 6 core dimensions | Data governance and DQ practitioners | No — book/chapter content; the *list* is what gets encoded into schemas like ODCS `dimension:` or DQV dimensions [34][35][36] | DAMA International owns DMBOK; DAMA UK's six dimensions are adopted as the reference set in UK government guidance [34][35][36] | Zero as an artifact; the cost is assigning each published metric to a named dimension |

## 3. What is genuinely expected of a public trust-layer product

**Tier 1 — a reviewer notices the absence.**
1. **schema.org/Dataset + DataCatalog JSON-LD** on stable, dereferenceable URLs, one node per described dataset [16]. Lowest-cost, highest-recognition artifact; adoption is at web scale [16].
2. **DCAT 3-conformant catalog description** (or an explicit mapping), separating dataset, distribution, data service and series [5]. For a national or EU-facing audience, DCAT-AP conformance is what a harvester checks, and it is machine-checkable [11][12].
3. **Quality assertions in DQV terms, or a documented equivalent with an explicit mapping** — dimension, metric, measurement, who measured it, when [9]. The most defensible "we are a verification layer, not a publisher" artifact, because DQV is designed for third-party annotation [9].
4. **Licence, provenance, version and persistent-identifier statements per the DWBP checklist** [17] — DWBP reads as an audit checklist, and its practices map 1:1 onto what a data buyer asks (what licence? who published it? when did it change? can I cite a stable ID?).
5. **A data contract for your own published surfaces** (ODCS-shaped): schema, quality rules, SLA, roles, version [18]. A buyer consuming your API needs your contract, not the upstream publisher's.
6. **Metrics labelled with named quality dimensions** (DAMA: timeliness, completeness, accuracy, consistency, …) so "freshness" is legible against an industry vocabulary rather than a bespoke taxonomy [34][35][36].

**Tier 2 — expected in a specific context.**
- **DataCite DOI + citation block** if you want to be cited by researchers rather than merely linked [26][28].
- **FAIR self-assessment with reproducible metric tooling** if the audience is research infrastructure; a bare "we are FAIR" claim without metric output is unverifiable [30][31].
- **ODPS** if you market the thing as a priced data product; adoption evidence is thin, so treat it as positioning, not a gate [21][22].
- **Croissant** only if you distribute ML datasets. A read-only verifier of portal APIs has no `FileObject`/`RecordSet` to describe; attaching Croissant to data you do not host is a category error [4][6].

**Tier 3 — optional, or actively wrong for a verifier.**
- **Datasheets for Datasets** [1] and **Data Statements** [2][3] are publisher-authored prose about data you own. A verifier can *link* to a publisher's datasheet, but shipping its own would assert composition and collection facts it cannot know. Optional as a link; wrong as an artifact.
- **Frictionless Data Package** [8] presumes you package and deliver the data. Wrong if you never redistribute; useful only if you mirror.
- **Data mesh** is architecture vocabulary, not a document type — citing "data product" without an artifact invites the question "which file?" [23].
- **"Dataset passport"** is not an adopted standard name [32][33]. Naming your own artifact that way is fine only if you publish its schema, version and conformance claims so a reviewer can map it.

## 4. Where DataPulse already stands (local inspection, /home/redza/datapulse-dev, 2026-09-26)

- `scripts/gen_jsonld_catalog.py` and `data/jsonld/*.json` emit `@type: Dataset` with name, description, url, `sameAs`, identifier, keywords, creator, publisher, spatialCoverage, licence — **Tier 1.1 covered, partially** (no `distribution`, no `DataCatalog` wrapper in the excerpt inspected).
- `datacontract/datapulse.contract.yaml` declares `apiVersion: v3.1.0` with `dimension: completeness` and `dimension: conformity` checks — **ODCS-shaped, Tier 1.5 covered**.
- `passport.schema.json` v1 carries `quality_profile.dimensions` = fair, licensing, provenance, governance, reproducibility, catalogue_readiness — bespoke, **not** expressed in DQV/DCAT terms and not mapped to DAMA dimension names. That mapping is the cheapest remaining Tier-1 gap.
- `docs/enterprise-governance.md`, `trust-contract.md`, `evidence-receipt-spec.md`, `documentation-map.md` are buyer-facing governance documents that sit outside every external standard above — and are what a procurement reviewer actually reads.
- The repo's own 2026-08-27 research note already identifies DCAT 3, schema.org Dataset/DataCatalog and PROV-O as "adopt now", which agrees with Tier 1 above.

## Sources (all retrieved 2026-09-26)

Identifiers embedded in reference URLs (DOIs, article numbers, date path segments) are reproduced verbatim from retrieval; the ones flagged below were re-verified with a command, the rest are **unverified** as identifiers beyond the retrieval itself.

1. https://arxiv.org/abs/1803.09010v8 — Datasheets for Datasets v8; publication record https://dl.acm.org/doi/10.1145/3458723 (DOI verified via Crossref on 2026-09-26: CACM 64(12):86–92)
2. https://aclanthology.org/Q18-1041.pdf — Bender & Friedman, TACL 6:587–604
3. https://techpolicylab.uw.edu/data-statements/ — data statements schema v1–v3
4. https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html — Croissant 1.1, published 2026-01-29
5. https://www.w3.org/TR/vocab-dcat-3/ — DCAT 3, W3C Recommendation 22 Aug 2024
6. https://docs.mlcommons.org/croissant/ — integrations: Dataset Search, Kaggle, OpenML, Hugging Face
7. https://papers.nips.cc/paper_files/paper/2024/file/9547b09b722f2948ff3ddb5d86002bc0-Paper-Datasets_and_Benchmarks_Track.pdf — Croissant paper, 400,000+ datasets. The hex string is a path segment of the served URL (verified 2026-09-26 to resolve HTTP 200, 1,229,547 bytes); it is not a checksum computed here.
8. https://specs.frictionlessdata.io/data-package/ and https://datapackage.org/blog/2024-06-26-v2-release/ — Data Package v1 and v2
9. https://www.w3.org/TR/vocab-dqv/ — Data Quality Vocabulary
10. https://github.com/frictionlessdata/ckanext-datapackage and https://datist.io/blog/2025-09-01-data-package-on-zenodo/ — CKAN endpoint, Zenodo export
11. https://semiceu.github.io/DCAT-AP/releases/3.0.1/ — DCAT-AP 3.0.1, SEMIC Recommendation 2025-10-27
12. https://dataeuropa.gitlab.io/data-provider-manual/our-metadata-model/ — EDP metadata model and MQA
13. https://data.europa.eu/sites/default/files/course/Slides%20webinar%20for%20data%20providers%20%C2%B4Data.europa.eu%20-%20The%20official%20portal%20for%20European%20data%60.pdf — 170+ catalogues, 1.4M+ datasets
14. https://eur-lex.europa.eu/eli/reg_impl/2023/138/ojt — Implementing Regulation (EU) 2023/138
15. https://semiceu.github.io/DCAT-AP/drafts/3.0.1-hvd/ — DCAT-AP for High-Value Datasets
16. https://schema.org/Dataset — usage estimate 10K–100K domains (Google web index, July 2026)
17. https://www.w3.org/TR/dwbp/ — DWBP, W3C Recommendation 31 Jan 2017, 35 best practices
18. https://github.com/bitol-io/open-data-contract-standard and https://bitol-io.github.io/open-data-contract-standard/v3.1.0/
19. https://lfaidata.foundation/blog/2023/11/30/bitol-joins-lf-ai-data-as-new-sandbox-project/ (URL and page title verified 2026-09-26)
20. https://github.com/paypal/data-contract-template — origin of ODCS
21. https://opendataproducts.org/v4.1/ — ODPS 4.1, release date 24 Oct 2025
22. https://github.com/Open-Data-Product-Initiative/v4.1 — Apache-2.0, star count as observed
23. https://martinfowler.com/articles/data-mesh-principles.html — four principles; data product components
24. https://martinfowler.com/articles/data-monolith-to-mesh.html — discoverable/addressable/trustworthy/self-describing
25. https://www.ibm.com/think/topics/data-mesh — data product definition (secondary source)
26. https://schema.datacite.org/ — DataCite Metadata Schema 4.7, released 3 Mar 2026
27. https://datacite-metadata-schema.readthedocs.io/en/4.6/properties/overview/ — Table 1 mandatory properties
28. https://datacite.org/blog/100-million-datacite-dois-more-than-just-a-number/ — 100M DOIs, ~3,900 repositories
29. https://datacite.org/blog/expanding-access-to-datacite-metadata-new-public-and-monthly-data-files-now-available/ — 2025 public data file, 108M DOIs
30. https://www.go-fair.org/fair-principles/ — FAIR principles F1–R1.3
31. https://www.f-uji.net/ — F-UJI automated FAIR assessment (FAIRsFAIR metrics)
32. https://arxiv.org/html/2506.22358v1 — AI Model Passport / AIPassport, incl. a "Data Passport" notion (research prototype)
33. https://pubs.aip.org/aip/bpr/article/7/3/031305/3403506/ — imaging "dataset passport" reporting structure (domain proposal). Volume/issue 7/3 corroborated by Crossref (DOI 10.1063/5.0341991, *Biophysics Reviews*); the article number `3403506` is an AIP-internal path segment taken verbatim from the search result and **not independently verified** (publisher returned HTTP 403 on 2026-09-26).
34. https://dama.org/dama-dmbok-revision/ and https://www.damadmbok.org/dmbok2-revisions — DMBOK2 revision: 9 standard dimensions, currency added
35. https://www.dqglobal.com/wp-content/uploads/2013/11/DAMA-UK-DQ-Dimensions-White-Paper-R37.pdf — DAMA UK six core dimensions
36. https://www.gov.uk/government/news/meet-the-data-quality-dimensions — UK government adoption of DAMA UK dimensions
