# ODIN export path — 2026-10-04

**Subject:** the ODIN (Open Data Inventory) open-data assessment published by Open Data
Watch at `odin.opendatawatch.com`.

**Question this lane answered:** is there a deterministic path to ODIN's data that a
probe can point at, or is the data only produced client-side inside a single-page
application?

**Verdict:** a deterministic, unauthenticated **JSON API** exists and is the real data
path. It is `https://odin-aim.akroninc.net/api/api/`, declared in the site's own
JavaScript bundle. Seven GET endpoints were measured on 2026-10-04 and onboarded as
static-reference rows. The **scored** assessment (country scores and ranks) is
additionally exposed but through **POST-only** endpoints (and a bulk static ZIP); the
static-reference probe shape is a single-URL GET, so the scored payloads are documented
here and deliberately **not** onboarded. No interface was scraped and no path was
guessed.

Observed: 2026-10-04. All fetches were bounded (`curl --max-time`).

---

## 1. How the data path was found

1. `GET https://odin.opendatawatch.com/` → `HTTP 200 text/html`, 15,507 bytes. This is an
   Angular SPA shell. The served HTML enumerates these `src`/`href` targets:
   `main-W5ZEWZSK.js`, `polyfills-FFHMD2TL.js`, and ten `chunk-*.js` bundles, plus
   `ammap/ammap.js` and `ammap/maps/js/worldWTLow.js`. The HTML body contains no
   assessment data.
2. Fetching every listed bundle returned `HTTP 200 application/javascript`. Parsing them
   yielded the origin constant:
   ```js
   var Oe={production:!0,apiUrl:"https://odin-aim.akroninc.net/api/api/",
           siteUrl:"https://odin-aim.akroninc.net/"};
   ```
   and the API service methods that address it (exact path literals, section 2).
3. The bundles also reference lazy chunks not in the initial HTML (for example
   `chunk-KD533IRJ.js`); those were fetched too. The download page lives in
   `chunk-HLDS23A4.js`, which showed the `DataDownload` request body and the bulk
   download label.

## 2. Exact network targets found in the bundle

Origin: `https://odin-aim.akroninc.net/api/api/`

GET endpoints (all deterministic, no auth):

| # | Path | Onboarded as |
|---|------|--------------|
| 1 | `client/GetLiveYears` | `odin_editions` |
| 2 | `client/GetCountries` | `odin_countries` |
| 3 | `client/GetRegions` | `odin_regions` |
| 4 | `client/GetIncomeGroups` | `odin_income_groups` |
| 5 | `client/GetContinents` | `odin_continents` |
| 6 | `client/GetLatestsCategories` | `odin_categories` |
| 7 | `client/GetDefaultWeights` | `odin_default_weights` |
| — | `client/IsInMaintnenaceMode` | not a dataset (boolean flag) |
| — | `client/GetLastUpdatedDate` | not a dataset (a display string) |
| — | `client/GetLatestNews` | not a dataset (news item) |
| — | `client/GetAvailableCountries/{useId}` | per-edition slice of `odin_countries`; see §6 |
| — | `client/GetAvailableYearsForCountry/{countryId}` | lookup |
| — | `client/GetCountryRanksForRegion/{regionId}/{useId}` | chart config with embedded JS |
| — | `client/GetRegionalProfile[/{id}]` | UI profile blob |
| — | `client/GetMultiCountryCompareProfile[/{id}]` | UI profile blob |
| — | `client/GetLatestsCategories/{id}` | empty (`[]`) for the ids tried |
| — | `client/GetReportData/{useId}` | HTTP 500 for every id tried (1,3,4,5,7,8,9) |
| — | `client/DownloadStaticFile/{name}/{type}` | binary file download; see §5 |

POST endpoints (scored assessment and exports; a GET returns HTTP 405):

`client/GetGlobalMapData/{useId}`, `client/GetUniversalScores/{useId}`,
`client/GetRanking/{useId}`, `client/GetScoresForElement/{useId}/{elementId}`,
`client/GetCountryScore/{useId}/{countryId}`, `client/GetCountryProfile/{useId}/{countryId}`,
`client/GetCountryRanksForRegion/{regionId}/{useId}`, `client/GetCountriesWithReportInRegion`,
`client/GetRegionalProfileData/{a}/{b}/{c}`, `client/GetMultiCountryCompareProfileData`,
`client/GetMultiYearCountryProfile/{a}/{b}`, `client/CalculateWeights`, `client/SaveContact`,
`client/DataDownload`, `client/DataDownloadPreview`, `client/GetRankingsExport/{a}/{b}/{c}`,
`client/GetRegionViewExport/{a}/{b}/{c}/{d}`,
`client/GetComparisonViewExport/{a}/{b}/{c}/{d}`,
`clientReport/ExportCountryReport/{a}/{b}`, `clientReport/ExportRegionReport/{a}/{b}`,
`clientReport/ExportCountryRecommendations/{a}`.

Same-origin static file: `settings.json` (licence and citation strings; §4).

## 3. Measured raw response shapes (2026-10-04)

All seven onboarded endpoints returned `HTTP 200`, `content-type:
application/json; charset=utf-8`.

| Dataset | URL | Bytes | Shape | First-record keys |
|---|---|---|---|---|
| `odin_editions` | `.../client/GetLiveYears` | 1,210 | JSON array, 7 items | `useId, year, description, dataCollecting, isLive, dateAdded, dateUpdated, dataUpdatedAt` |
| `odin_countries` | `.../client/GetCountries` | 79,590 | JSON array, 243 items | `countryId, regionId, incomeGroupId, incomeRegionId, developingRegionId, countryCode, countryName, isInMap, nsoUrl, isSmallCountry, accentedCountryName, disseminationSubscriber, preferedLanguage, region, continent` |
| `odin_regions` | `.../client/GetRegions` | 3,031 | JSON array, 21 items | `regionId, continentId, shortName, fullName, centerLatitude, centerLongitude, continent` |
| `odin_income_groups` | `.../client/GetIncomeGroups` | 442 | JSON array, 5 items | `incomeGroupId, incomeCode, incomeGroup1, orderNumb` |
| `odin_continents` | `.../client/GetContinents` | 372 | JSON array, 6 items | `continentId, continentCode, continent1` |
| `odin_categories` | `.../client/GetLatestsCategories` | 8,702 | JSON array, 23 items | `categoryId, categoryGroupId, category1, recommendedDisaggregation, representativeIndicators, orderNum, prevYearCategoryId, yearId, projectId, initial, categoryGoals, categoryInputs, indicators, sdgGategoryGoals` |
| `odin_default_weights` | `.../client/GetDefaultWeights` | 54,676 | JSON object, 52 top-level keys | `allCriteriaSumWeights, categories, categoriesEnabledInGrp1..3, category1Weight..category23Weight, categoryGroups, coverageSumWeights, criteria, criteria1Weight..criteria10Weight, criteriaGroups, customWeights, groupOneSumWeights..groupThreeSumWeights, normalizedFinalWeights, opennessSumWeights, selectedWeightType, selectedYear, smallCountriesCustomWeights, weightSelection` |

The edition list carries the publisher's own edition dates inside the data, for example
`{"useId":9,"year":2024,"description":"2024/2025","dataUpdatedAt":"July 21, 2025"}` and
`client/GetLastUpdatedDate` returns `{"lastUpdatedAt":"Last updated: July 21, 2025"}`.
The catalogue records these as **fields of the data**, not as an invented freshness band:
every onboarded row is `data_type: reference` with no `content_freshness_date`, no
cadence, and no `freshness_policy`.

### Scored payloads (POST; measured with a fixed `{}` body)

- `POST .../client/GetGlobalMapData/9` → JSON array of
  `{Id, CountryId, CountryName, CountryCode, OverallScore, GlobalRank, RegionalRank, Color, SelectedColor}`.
- `POST .../client/GetRanking/9` → JSON array of
  `{countryId, countryCode, countryName, regionCode, regionName, regionId, continentId, continent, coverageSubscore, opennessSubscore, rowTotalSubscore, rank}`.
- `POST .../client/GetUniversalScores/9` → JSON object
  `{universeScores:{overall,coverage,openness}, countryWithAssessmentsCount, ...}`.
- `POST .../client/GetCountryScore/9/{countryId}` → JSON object of one country's scores
  and ranks.
- `GET` on any of the above returns **HTTP 405 Method Not Allowed** (`Allow: POST`).

## 4. Licence and the attribution obligation

The licence is **CC BY 4.0**, and it was found in the application's own assets, not
guessed from the served HTML (which does not state it):

- Served asset `settings.json` (`HTTP 200 application/json`, 602 bytes):
  ```json
  {
    "ExportFooterLine1": "©2020 Open Data Watch - Licensed under a Creative Commons Attribution 4.0 license",
    "ExportFooterLine2": "Please cite any uses of these data as: Open Data Watch -- Open Data Inventory http://www.opendatawatch.com"
  }
  ```
- The bundle contains the rendered footer string
  `"©",i.year," Open Data Watch - Licensed under a Creative Commons Attribution 4.0 license"`.

Consequences applied to the catalogue:

1. Every onboarded row records the SPDX identifier `CC-BY-4.0` — not the phrase
   "Creative Commons Attribution 4.0".
2. CC BY 4.0 requires attribution, so every row carries:
   `"Open Data Watch -- Open Data Inventory (ODIN), https://odin.opendatawatch.com. Licensed under CC BY 4.0."`
   and `steward: "Open Data Watch"`, registered as custodian `odin` in
   `custodians.json`.
3. Generated surfaces that reproduce ODIN content carry that attribution from the
   manifest:
   - `scripts/gen_dataset_pages.py` → `Licence`/`Attribution` on the public
     `docs/datasets/<id>.html` page and in its JSON-LD `additionalProperty`.
   - `scripts/gen_json_envelope.py` → the `attribution` field, built from
     `source` (`"Open Data Watch -- Open Data Inventory"`) + namespace.
   - `scripts/gen_dataset_passports.py` → `licence_and_attribution.attribution`.
   - `scripts/gen_okf_bundle.py` → `datapulse:licence` / `datapulse:attribution`.
   - `scripts/gen_quality_profile.py` → `licensing.declared_attribution`.
   The status badges, the dashboard register index, and the private `data/<id>.md`
   health report carry dataset identity, status and probe measurements only; they do
   not reproduce ODIN's data values and link to the attributed public dataset page.

## 5. The bulk export is a POST-assembled / binary download, not a JSON/CSV file

The download page (`chunk-HLDS23A4.js`) builds this request body and POSTs it:

```js
{ selectedYears, selectedRegions, selectedCountries, scoreType,
  outputFormat /* "CSV" | "Excel" | "JSON" */, dataOrientation,
  includeSubtotals, includeNotes, isPreview, weights }
```

`POST .../client/DataDownload` returns the file as a blob (`responseType:"blob"`), so the
export is assembled **client-side** from the user's selection. There is no static
CSV/JSON export URL. A static bulk file does exist behind a GET —
`GET .../client/DownloadStaticFile/2016-2024%20data.zip/bulkDownload` — measured as
`HTTP 200 application/octet-stream`, `Content-Length: 7831186`,
`Content-Disposition: attachment; filename="2016-2024 data.zip"`, with ZIP magic `PK\x03\x04`
and first member `2016.xlsx`. It is a 7.8 MB archive of per-edition `.xlsx` workbooks.

## 6. What was onboarded, and what was not

**Onboarded** — seven GET JSON endpoints, in the static-reference shape used by the DOSM
and MECo layers (`adapter: direct`, `format: json`, `freshness: structural-hash` /
`unknown-freshness`), ids added to `scripts/contract-scope.json`:

`odin_editions`, `odin_countries`, `odin_regions`, `odin_income_groups`,
`odin_continents`, `odin_categories`, `odin_default_weights`.

`client/GetAvailableCountries/{useId}` was **not** onboarded separately: it is the
per-edition projection of `odin_countries` (243 countries in the universe, with
`isInMap` marking the assessed ones), and onboarding both would double-count the same
data in two shapes.

**Not onboarded, and why:**

- The scored assessment (`GetGlobalMapData`, `GetRanking`, `GetCountryScore`,
  `GetUniversalScores`, `DataDownload`, the `*Export*` endpoints) is **POST-only**. The
  probe-policy `direct` adapter addresses one `url` with a GET and has no request-body
  field, so it cannot express these. Proxying or scraping them would put an
  unverifiable claim into the trust layer.
- `client/DownloadStaticFile/2016-2024 data.zip/bulkDownload` is a real deterministic
  GET, but the probe `format` enum (`csv, json, geojson, html, xml, pdf, parquet`) has no
  archive/xlsx member, and a 7.8 MB archive is not a bounded per-cycle probe.

**What would be required to onboard the scored data deterministically:** either

1. a probe adapter that can issue a fixed-body POST and treat the response as a
   structural-hash reference surface (a probe-policy schema extension), or
2. an upstream static JSON/CSV file for the scores that does not exist here today.

Until one of those exists, this lane reports the path and does not publish the scores.

## 7. Generated surfaces the generation profile must produce

This lane did not run the generation profile. The following generated artifacts must be
produced (and committed) before the repository contract is satisfied for the new rows:

- `data/<id>.md` — health report (from the probe run).
- `data/jsonld/<id>.json` and `docs/datasets/<id>.html` — public attributed pages
  (`scripts/gen_dataset_pages.py`); note the page JSON-LD must carry the attribution.
- `data/json/<id>.json` — dataset-health envelopes (`scripts/gen_json_envelope.py`),
  gated by the approved ids added to `scripts/contract-scope.json`.
- `badges/<id>.svg` — status badges.
- `data/passports/<id>.json` — dataset passports (`scripts/gen_dataset_passports.py`).
- `catalog-snapshot.json`, `catalog-graph.json`, `docs/.dashboard_*.json`,
  `docs/index.html`, OKF bundle, and the AI catalogue — regenerated from the manifest.

The manifest rows were added by hand (the established DOSM/MECo onboarding pattern); the
next probe cycle and generation profile will populate the health and public surfaces.
