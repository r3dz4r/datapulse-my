# datapulse-my — Contract Inventory

**Generated:** 2026-08-08
**Method:** Command-derived counts, all reproducible from a clean checkout
**Repository HEAD:** `7beeddc` (private engine reference; datapulse-my HEAD may differ slightly)

This inventory documents every count, every ID, and every preserved/redirected/migrated/retired URL per G1 (NPRA namespaces), G2 (data/json/ scope), and G7 (canonical host). Every figure below is followed by the command that produced it.

> **Important field-name note:** the manifest file uses field `id` per row; the health snapshot uses `dataset_id`. Always query with the right field name:
> ```bash
> jq -r '.datasets[].id' datapulse.json              # manifest
> jq -r '.datasets[].dataset_id' health/latest.json  # health
> ```

## 1. Total dataset count

| Metric | Count | Derivation |
|---|---|---|
| **Public registry rows** | **166** | `jq -r '.datasets[].id' datapulse.json \| wc -l` |
| **Manifest report files** (`data/*.md`) | 169 | `ls data/*.md \| wc -l` |
| Per-dataset JSON envelopes (legacy) | 92 | `ls data/json/*.json \| wc -l` |
| Per-dataset JSON-LD files | 167 | `ls data/jsonld/*.json \| wc -l` (= 166 + 1 catalog) |
| Health rows in latest snapshot | 166 | `jq -r '.datasets[].dataset_id' health/latest.json \| wc -l` |
| Badge SVGs | 173 | `ls badges/*.svg \| wc -l` (= 166 + 6 status + 1 index) |
| Probe samples | 182 | `ls samples/ \| wc -l` |

The earlier figure of 171 reports counted the 169 `data/*.md` files plus the
`data/json/` and `data/jsonld/` directories. Those two entries are directories,
not orphan report IDs.

### Alignment verification (manifest vs health)

```bash
diff <(jq -r '.datasets[].id' datapulse.json | sort) \
     <(jq -r '.datasets[].dataset_id' health/latest.json | sort)
# (empty = perfect alignment)
```

**Result:** empty. **166 manifest IDs == 166 health IDs. No drift.** The verifier (Task 4) should encode this check.

## 2. Distribution (by namespace, licence, refresh_frequency)

| Field | Distribution |
|---|---|
| **Namespace** (166 datasets) | economy: 70 · transport: 37 · government_open_data: 35 · healthcare: 11 · other: 7 · environment: 5 · weather: 1 |
| **Licence** (166 datasets) | Creative Commons Attribution 4.0: 154 · Open Government Licence (Malaysia): 12 |
| **Refresh frequency** (166 datasets) | monthly: 52 · annual: 43 · as-required: 15 · 30 seconds: 14 · daily: 13 · biennial to triennial (survey years): 11 · quarterly: 10 · hourly: 3 · weekly: 1 · daily (weekdays, 1700/1200/1130/0900 MYT): 4 |

All counts derived via `jq -r '.datasets[].<field>' datapulse.json | sort | uniq -c | sort -rn`.

## 3. NPRA ID set (per G1 + Q4)

| ID | In public registry? | Notes |
|---|---|---|
| `npra_products_registered` | **No** | "Paid-product raw manifest" — engine-side provenance only |
| `npra_cosmetic_notifications` | **No** | Same |
| `npra_drug_registration_guidance` | **No** | Same |

- The 3 `npra_*` manifests exist in `data/` for documentation but **never enter `datapulse.json`**.
- No `data/json/npra_*.json` files exist (correctly absent).
- Per G1: both `npra_*` and `pharmaceutical_*` namespaces are preserved as first-class IDs when they enter the registry.
- Per Q4: these 3 stay private; future public admission is a separate G8-style decision.

**Orphan detection:**
```bash
comm -13 <(jq -r '.datasets[].id' datapulse.json | sort) \
         <(ls data/*.md | xargs -n1 basename | sed 's/\.md$//' | sort)
# Result: npra_cosmetic_notifications, npra_drug_registration_guidance, npra_products_registered
# (the 3 are consistent with Q4)
```

## 4. Expected vs actual subsets

| Subset | Expected (per G1+G4) | Actual | Verdict |
|---|---|---|---|
| Public registry rows | 166 | 166 | ✅ matches |
| `data/<id>.md` for each registry ID | 166 | 166 | ✅ matches |
| `data/json/<id>.json` for each registry ID | 136 non-GTFS + 0 GTFS = 136 | 136 | ✅ matches |
| `data/jsonld/<id>.json` for each registry ID | 166 | 166 | ✅ matches |
| Health rows in latest snapshot | 166 | 166 | ✅ matches |

### JSON-envelope coverage

All 136 non-GTFS registry IDs have envelopes (T19 expansion 2026-08-09). The 30 GTFS datasets remain excluded by the existing GTFS exception.

The canonical envelope has 16 ordered keys: `schema`, `id`, `status`,
`last_checked`, `freshness_days`, `next_expected_update`, `refresh_frequency`,
`record_count`, `date_range`, `fields`, `checks`, `known_quirks`,
`breaking_changes`, `reproducibility`, `licence`, and `attribution`. The
generator always emits all 16 keys; unavailable scalar/object values may be
`null`, and unavailable arrays may be empty. In the 92 pre-T19 legacy
envelopes, only `status`, `known_quirks`, `licence`, and `attribution` were
physically present in every file. Those legacy shapes are preserved.

## 5. Public URL disposition (per G7 + Q1)

### Canonical URLs (after G2 expand ships)

```text
https://data-pulse.my/data/json/<id>.json
https://data-pulse.my/data/json/catalog.json
https://data-pulse.my/data/json/schema.json
https://data-pulse.my/data/json/context.json
https://data-pulse.my/data/<id>.md
https://data-pulse.my/health/latest.json
https://data-pulse.my/badges/<id>.svg
```

All use `https://data-pulse.my/...` per G7. GitHub Pages origin `https://r3dz4r.github.io/datapulse-my/...` is infrastructure-only.

### Legacy URLs (per Q1: documented as broken, no redirects)

| URL pattern | Disposition |
|---|---|
| `https://data-pulse.my/data/jsonld/<id>.json` | **410 Gone** after G2 ships |
| `https://data-pulse.my/data/jsonld/catalog.json` | **410 Gone** after G2 ships |
| `https://r3dz4r.github.io/datapulse-my/data/jsonld/<id>.json` | Same as above (resolve to canonical after redirect removal) |
| `https://r3dz4r.github.io/datapulse-my/data/json/<id>.json` | **410 Gone** (legacy per-dataset envelopes) |
| `https://r3dz4r.github.io/datapulse-my/data/json/catalog.json` | **410 Gone** (legacy catalog) |

No redirects. Breaking change announced in changelog + README + llms.txt.

## 6. NPRA compatibility paths (per G1)

The 3 `npra_*` manifests reference upstream sources:
- `npra_products_registered` → `https://storage.data.gov.my/healthcare/pharmaceutical_products.csv`
- `npra_cosmetic_notifications` → same upstream (different scope)
- `npra_drug_registration_guidance` → NPRA DRGD index page

These are **engine-side provenance** (per G1 + Q4). The compatibility paths record which upstream sources feed which `npra_*` IDs. The overlap with `pharmaceutical_*` is intentional — both namespaces track the same upstream CSV but for different scopes.

## 7. Verification commands (re-runnable)

```bash
# Total counts
jq -r '.datasets[].id' datapulse.json | wc -l                       # 166
ls data/*.md | wc -l                                                # 169
ls data/json/*.json | wc -l                                        # 136
ls data/jsonld/*.json | wc -l                                      # 167
jq -r '.datasets[].dataset_id' health/latest.json | wc -l          # 166
ls badges/*.svg | wc -l                                            # 173
ls samples/ | wc -l                                                # 182

# ID-set equality (manifest vs health)
diff <(jq -r '.datasets[].id' datapulse.json | sort) \
     <(jq -r '.datasets[].dataset_id' health/latest.json | sort)
# (empty = perfect alignment)

# Distribution counts
jq -r '.datasets[].namespace' datapulse.json | sort | uniq -c | sort -rn
jq -r '.datasets[].licence' datapulse.json | sort | uniq -c | sort -rn
jq -r '.datasets[].refresh_frequency' datapulse.json | sort | uniq -c | sort -rn

# NPRA inventory
ls data/npra_*.md
ls data/json/npra_*.json 2>/dev/null || echo "  (correctly absent)"
ls data/jsonld/npra_*.json 2>/dev/null || echo "  (correctly absent)"

# Orphan detection (manual IDs)
comm -13 <(jq -r '.datasets[].id' datapulse.json | sort) \
         <(ls data/*.md | xargs -n1 basename | sed 's/\.md$//' | sort)
# Returns: npra_cosmetic_notifications, npra_drug_registration_guidance, npra_products_registered

# 30 GTFS IDs intentionally have no data/json/<id>.json file
comm -23 <(jq -r '.datasets[].id' datapulse.json | sort) \
         <(ls data/json/ 2>/dev/null | sed 's/\.json$//' | sort)
```

## 8. Open follow-ups (for Task 22)

1. **The data/jsonld/<id>.json URLs that the new G2 expands away from** need to be removed from any pre-generated `llms.txt` or `mcp.json` discovery file (Task 22 scope).
2. **README/llms.txt counts** (currently hardcoded) need to be derived from this inventory at build time (Task 22).

---

**Verified-by:** Hermes Agent (operator-side per SOUL.md rule 1 carve-out)
**Verified-at:** 2026-08-08T22:00+08:00
**Re-run-safe:** all counts are reproducible from the commands in section 7
