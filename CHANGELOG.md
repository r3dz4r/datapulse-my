# Changelog

This is the chronological project history. Live dataset state belongs in
[`health/latest.json`](health/latest.json) and generated machine-readable state
belongs in [`changelog.json`](changelog.json).

## Version line re-based to 3.5.0 (2026-09-11)

Release numbering continues from the MCP Registry's existing `3.4.x` line rather than the
repository's previous `0.x` line. The registry determines a server's *latest* version by
comparing versions as semver across every published, non-deleted version, and its highest
published version was `3.4.6` — so a `0.x` release can never become the registry's latest and
consumers kept resolving a superseded entry. Publishing above `3.4.6` is the only mechanism the
registry provides. All earlier releases remain tagged and published; only the numbering continues
from this point.

## [3.7.0](https://github.com/r3dz4r/datapulse-my/compare/v3.6.0...v3.7.0) (2026-09-13)


### Features

* **historic:** add the historical-observation envelope contract ([15098ea](https://github.com/r3dz4r/datapulse-my/commit/15098eaa96128fe04127b60fff0348bec80f8f97))

## [3.6.0](https://github.com/r3dz4r/datapulse-my/compare/v3.5.0...v3.6.0) (2026-09-12)


### Features

* **health:** fingerprint structure for non-tabular sources ([a7b0b36](https://github.com/r3dz4r/datapulse-my/commit/a7b0b366667850130faec1a69650d4c712d2c6df))
* **mcp:** attribute MCP requests to their source in the journal ([0746ed2](https://github.com/r3dz4r/datapulse-my/commit/0746ed2364d3a2be8600bd78b4b00177163ab4ad))
* **mcp:** declare usage ledger schema era ([33f0e1d](https://github.com/r3dz4r/datapulse-my/commit/33f0e1d03ce3be16effa5f4ee2673d7e5a6577be))
* **okf:** pin each Attested Computation's sources by content digest ([0b779f2](https://github.com/r3dz4r/datapulse-my/commit/0b779f26a575e2b1ddb23ca282ef820dd77e0aec))


### Bug Fixes

* **attestation:** stop the anchor job writing to the release PR branch ([8da3974](https://github.com/r3dz4r/datapulse-my/commit/8da3974a1d5054f989988b887d919880edbc2b6a))
* **attestation:** stop the anchor job writing to the release PR branch ([56b8686](https://github.com/r3dz4r/datapulse-my/commit/56b86866d355d26cdf1d3a388959aabff3a9c812))
* **health:** record shape_basis only as a positive finding ([1c6e264](https://github.com/r3dz4r/datapulse-my/commit/1c6e264bbccf82e065440eed25a12897f5439bd1))
* **mcp:** populate usage result summaries and classify usage errors ([a96163a](https://github.com/r3dz4r/datapulse-my/commit/a96163adce18d01a02dd27f2c48f301bf405523e))
* **okf:** bind Attested Computation trust state to the method ([dcd824f](https://github.com/r3dz4r/datapulse-my/commit/dcd824f7514de68dcb5bf9164569c412a9246862))
* **okf:** name the real attester in Attested Computation concepts ([a0090b0](https://github.com/r3dz4r/datapulse-my/commit/a0090b07e26488e14968d275368a7c738df3d3b8))

## [0.13.0](https://github.com/r3dz4r/datapulse-my/compare/v0.12.0...v0.13.0) (2026-09-11)


### Features

* **attestation:** enforce shared signing workflow contract ([80dd926](https://github.com/r3dz4r/datapulse-my/commit/80dd926b751cb10e384072ab70ee629ca53c25ba))
* **attestations:** enforce chain forward-linearity seed ([6d96ea4](https://github.com/r3dz4r/datapulse-my/commit/6d96ea47f9ce011511425a982e06dca6044a4ffb))
* **attestations:** forward Rekor reference into fresh-day binding generation ([d2912ea](https://github.com/r3dz4r/datapulse-my/commit/d2912ea34ed88167124a670a5e323f0a96bca4da))
* **audit:** extend HS-05 failure corpus ([b0f2e35](https://github.com/r3dz4r/datapulse-my/commit/b0f2e35186997371bb0f6d59d8299a4f740e6de3))
* **mcp:** add deterministic agent task suite ([dbcbdd0](https://github.com/r3dz4r/datapulse-my/commit/dbcbdd0df630a30af4e5f080509e480830ec491b))
* **mcp:** add privacy-preserving HTTP request correlation ([91d1813](https://github.com/r3dz4r/datapulse-my/commit/91d1813a0c565162469014fd4d8710a808e5b960))
* **mcp:** bind evidence tools to receipt digests ([be25713](https://github.com/r3dz4r/datapulse-my/commit/be2571329bc1d38b57b5766f3b77b07411b082fd))
* **mcp:** clarify citation and verification contract ([38f601d](https://github.com/r3dz4r/datapulse-my/commit/38f601d70d35a9984c672db2e38a6eb3231129f4))
* **mcp:** complete private MCPVerse benchmark lane ([3bb58e0](https://github.com/r3dz4r/datapulse-my/commit/3bb58e02e7c4172d59179d2b1afd792ee0dfc0f6))
* **mcp:** expose receipt digests ([4ff7deb](https://github.com/r3dz4r/datapulse-my/commit/4ff7debd8294f7825cd218ea6b3d272e6cb92b4d))
* **mcp:** improve tool selection metadata ([8345353](https://github.com/r3dz4r/datapulse-my/commit/83453539e83ef7cc3ed9973ac747e3d4fd80f668))
* **mcp:** optimize DataPulse discovery metadata ([f67c239](https://github.com/r3dz4r/datapulse-my/commit/f67c23982b1ed0ce77f4238fa77728f932a31f9b))
* **observability:** add sanitized pipeline run receipts ([fcb17e4](https://github.com/r3dz4r/datapulse-my/commit/fcb17e448a0f55d2e0c61ecb02fb2785e2b1475a))
* **passport:** complete evidence-bounded dataset passport contracts ([586f601](https://github.com/r3dz4r/datapulse-my/commit/586f601d47c89eef7e9ae25f66444e7356c84838))
* **public:** add datapulse_summary.json rollup for downstream consumers ([cf3f394](https://github.com/r3dz4r/datapulse-my/commit/cf3f3948c78d87419d73a06085bb7fa52d084a44))
* **quality:** publish additive six-dimension readiness profiles ([7584a4e](https://github.com/r3dz4r/datapulse-my/commit/7584a4e623b543a65b7074233b8727d54b394166))
* **readme:** full deterministic README auto-generator (owned-block composition) ([006e416](https://github.com/r3dz4r/datapulse-my/commit/006e4169e1593ab15708238205134383eca37864))
* **release:** bind preview and production to one artifact ([0919413](https://github.com/r3dz4r/datapulse-my/commit/0919413c6ec832554d621090b49b0cacd5e375e3))
* **release:** one version authority with a fail-closed identity gate ([9840d17](https://github.com/r3dz4r/datapulse-my/commit/9840d17853cb7d6943fe9622bd88c5341ef01e69))
* **sg:** enrich 5 Singapore dataset metadata from catalog API + static map ([e4b5300](https://github.com/r3dz4r/datapulse-my/commit/e4b530052e1972ee1f57870ed2d7327a0299d4ad))
* **shadow:** add non-authoritative health candidate contract ([91690a2](https://github.com/r3dz4r/datapulse-my/commit/91690a25d3588f04635d9d5d1cc111be43f3bc43))
* **trust:** add local evidence graph contract ([1c6644f](https://github.com/r3dz4r/datapulse-my/commit/1c6644f4eab0955c4d9d617d59ad45500c950ccd))
* **workflow:** add guarded Rekor producer to daily attestation workflow ([9013faa](https://github.com/r3dz4r/datapulse-my/commit/9013faaa84c29ef13ad2c62931478c40115ecf7a))


### Bug Fixes

* **attestations:** refresh_chain_head tolerates committed same-day dated set ([0f8d751](https://github.com/r3dz4r/datapulse-my/commit/0f8d751b673934742144ce4e44ce64d25bc18100))
* **attestations:** reuse valid same-day evidence ([27541ba](https://github.com/r3dz4r/datapulse-my/commit/27541ba0e196e6e14e9227f20edc191ae7bf7431))
* **ci:** authenticate release automation with a GitHub App token ([d292a32](https://github.com/r3dz4r/datapulse-my/commit/d292a32ac921af46bcc1cf7ed2fa428ecf5a1d56))
* **ci:** authenticate the anchor job with the App token too ([f82bc80](https://github.com/r3dz4r/datapulse-my/commit/f82bc800ac33517644ae9ae7cfca784123cef1bd))
* **ci:** classify generated passports and public summary as health-cycle outputs ([7a10708](https://github.com/r3dz4r/datapulse-my/commit/7a107087503c6ff5862f3b39a6b68c78680d834d))
* **ci:** classify health badge outputs correctly ([22603b4](https://github.com/r3dz4r/datapulse-my/commit/22603b4d25ed0317316dbe6521e544eb38043339))
* **ci:** give release automation a non-GITHUB_TOKEN credential ([f702381](https://github.com/r3dz4r/datapulse-my/commit/f702381f064fa376e675c9ee4e9c2a466546addb))
* **ci:** harden production attestation gate ([f6eb99f](https://github.com/r3dz4r/datapulse-my/commit/f6eb99f3360d4fa034fd57d2e9ada82a45a461db))
* **ci:** isolate health-only workflow runs ([0a4c518](https://github.com/r3dz4r/datapulse-my/commit/0a4c518e88ecfe34690370cf58c8b7d04b391c4a))
* **ci:** make release reproducibility deterministic with a shared envelope source cache ([db6388d](https://github.com/r3dz4r/datapulse-my/commit/db6388d741b79ea11a24c4a93e19baab74e66775))
* **ci:** restore audit contract fixtures ([829a23f](https://github.com/r3dz4r/datapulse-my/commit/829a23f99a79fab4ca4fc60ac49b2aed852f6ff2))
* **ci:** separate README generation from health commits ([16482fa](https://github.com/r3dz4r/datapulse-my/commit/16482fa801c155801b72e9eefba279d2e35b7a07))
* **discovery:** register agent catalog and workflow routes ([497df77](https://github.com/r3dz4r/datapulse-my/commit/497df770c2235242cbaed467a013030004f35b4e))
* **docs:** align MCP tool counts with canonical catalogue ([15159fb](https://github.com/r3dz4r/datapulse-my/commit/15159fb95f3fce71f85131b8c66e7590b6ce5cd6))
* **docs:** link agent workflows markdown ([c9d0bba](https://github.com/r3dz4r/datapulse-my/commit/c9d0bbab665009fc9d2702d444d562b043a3f579))
* **docs:** refresh generated MCP reference ([7ab25be](https://github.com/r3dz4r/datapulse-my/commit/7ab25be68961f4bed8549acbf3aa0f827b57ce4a))
* **health:** preserve unknown record tolerance ([5099d10](https://github.com/r3dz4r/datapulse-my/commit/5099d10a5cda715efe6c23f4d76f0d500a99fe41))
* **health:** record passport telemetry stage ([9ec6add](https://github.com/r3dz4r/datapulse-my/commit/9ec6add3d1a1e942a8d39b453ff590e88299b01b))
* **mcp:** correlate usage ledger and journal events ([2c66a1a](https://github.com/r3dz4r/datapulse-my/commit/2c66a1a2ea550b7986c354a3abbdc3c51dfb9811))
* **mcp:** enforce canonical public-surface facts ([db93b9e](https://github.com/r3dz4r/datapulse-my/commit/db93b9edf1c92e0e562ec4eab2d3ca8d62a6787e))
* **mcp:** guard source identity generation ([1cbf6bc](https://github.com/r3dz4r/datapulse-my/commit/1cbf6bc7d7a17e3248aa6ec83a32154a8e90c54e))
* **mcp:** preserve dev fixture source marker ([fdc34d9](https://github.com/r3dz4r/datapulse-my/commit/fdc34d9d56278f76fb95323ebd982a2b7b43967d))
* **mcp:** publish on content drift, not a version-string match ([67ca204](https://github.com/r3dz4r/datapulse-my/commit/67ca2044816eb45ab9b0b9fb6351280421a1a457))
* **mcp:** synchronize dataset passport health ([e8676e7](https://github.com/r3dz4r/datapulse-my/commit/e8676e7ed95903d2cf6840f92bf3e5ecc72181ed))
* **mcp:** use Starlette middleware wrapper ([fcae241](https://github.com/r3dz4r/datapulse-my/commit/fcae24120d86a7971000b566fb193db9e0510b8a))
* **pages:** publish public summary artifact ([5681d22](https://github.com/r3dz4r/datapulse-my/commit/5681d225d4a8cab3c73fc926982ee3e7692d857e))
* **release:** close the release path — identity gate, content-aware publication, release-safe tag semantics ([3b54718](https://github.com/r3dz4r/datapulse-my/commit/3b547180e4d2902eb28104e3f306b9dec39f46a8))
* **release:** make server.json release-managed by release automation ([4cc71bc](https://github.com/r3dz4r/datapulse-my/commit/4cc71bcbe7896073381b608babd0c0c17ccfd824))
* **release:** treat a tag behind the manifest as a release in flight ([8143177](https://github.com/r3dz4r/datapulse-my/commit/81431775e0267306bd06ec15326d6c2652b21d31))
* **schema:** allow title/description/publisher/last_updated_at/frequency on dataset ([59d6cc8](https://github.com/r3dz4r/datapulse-my/commit/59d6cc8324fee3205d759425489dd9c80169b0b5))
* **telemetry:** accept the passports stage in the run receipt summarizer ([bb01f54](https://github.com/r3dz4r/datapulse-my/commit/bb01f54580482d40c0eaed1b3a01c43d24cd6895))


### Performance Improvements

* **mcp:** reduce verification latency tail ([6e5e48a](https://github.com/r3dz4r/datapulse-my/commit/6e5e48a88195831fa04fd74acdc69904de668a24))


### Reverts

* roll back SG metadata enrichment (e4b53005 + 59d6cc83) ([9dcdeb7](https://github.com/r3dz4r/datapulse-my/commit/9dcdeb77fb5ab23415b24e4ee5862e2f450d0774))

## [0.12.0](https://github.com/r3dz4r/datapulse-my/compare/v0.11.0...v0.12.0) (2026-09-06)


### Features

* **agent:** add Malaysian public-data citation recipe ([9c45450](https://github.com/r3dz4r/datapulse-my/commit/9c45450fc30a08328755d86ef7b6974c7bd840f5))
* **audit:** add pinned mcpgrade replay script and drop hardcoded score from README ([746a075](https://github.com/r3dz4r/datapulse-my/commit/746a0756be5aaddb4b70ccc4cd31c158e2c3763f))
* **mcp:** add citation resource template ([a2a5ab7](https://github.com/r3dz4r/datapulse-my/commit/a2a5ab7c7624e257bf5760887252392661c1ffd3))
* **mcp:** publish citation resource metadata ([7b71f3c](https://github.com/r3dz4r/datapulse-my/commit/7b71f3c4cb14a7526c63792f5a680a5391252103))
* **release:** honour ALLOW_UNATTESTED_HEALTH bypass in release-build attestation step ([fbe06a9](https://github.com/r3dz4r/datapulse-my/commit/fbe06a91e0741c782692e882e1ab1c3e617724a3))


### Bug Fixes

* **ci:** align Pages preview branch alias ([bf9c65e](https://github.com/r3dz4r/datapulse-my/commit/bf9c65e172b47c1fb3fba045b252f7bc96446d22))
* **ci:** correct preview verifier shell quoting ([510dc19](https://github.com/r3dz4r/datapulse-my/commit/510dc1973747c46b5ec7b6fcaee5eebbae77e1dd))
* **ci:** reuse served verifier for preview promotion ([c6e1a1c](https://github.com/r3dz4r/datapulse-my/commit/c6e1a1c0d2543684f93c54d33815dfd4709388fa))
* **ci:** scope licence-source claim and align deploy-verify test with recorded stamp ([19c19bb](https://github.com/r3dz4r/datapulse-my/commit/19c19bbe5dcdc9a141d7cbb4da9bc8c7548ba851))
* **ci:** set executable bit on audit_mcpgrade.sh ([bc0acc6](https://github.com/r3dz4r/datapulse-my/commit/bc0acc638f72921036928c2ba627710438b3f4b0))
* **ci:** stage Pages artifact before production promotion ([dc776a8](https://github.com/r3dz4r/datapulse-my/commit/dc776a8d0442f58dbb1175ba68d79d5a2dd85613))
* **ci:** use bounded Pages preview alias ([4c5173f](https://github.com/r3dz4r/datapulse-my/commit/4c5173ff38e85cde83df06122f86ea3214df7208))
* **mcp:** align source identity markers ([2e508e4](https://github.com/r3dz4r/datapulse-my/commit/2e508e40e68597b7d1a684a8cea4f8fd2e58770d))
* **scripts:** read MCP deploy stamp from version suffix and compare to mcp.json ([7747eba](https://github.com/r3dz4r/datapulse-my/commit/7747eba5fda2b91652b74d9893adb94a5fc17bff))
* **tests:** rename mcp source-sync test to unique basename (pytest collision) ([6f8edce](https://github.com/r3dz4r/datapulse-my/commit/6f8edce7bb170539050a1f93223b646098cdde36))

## [0.11.0](https://github.com/r3dz4r/datapulse-my/compare/v0.10.0...v0.11.0) (2026-09-05)


### Features

* **data:** add current ST license registers ([2a5c559](https://github.com/r3dz4r/datapulse-my/commit/2a5c5597ae77fc98eb65cfa6b69ca36f48ab7c04))
* **data:** onboard 10 ST MyEnergyStats dashboards (HTML, CBAM lane) ([9edb24a](https://github.com/r3dz4r/datapulse-my/commit/9edb24a477ec7620bd09be90642230e7dddc3d8c))
* **data:** onboard 8 KKMNOW github live-tail parquet datasets ([7ebfbb7](https://github.com/r3dz4r/datapulse-my/commit/7ebfbb7253aecf3986d94678d5f7fa02cc124d03))
* **data:** onboard ST National Energy Balance 2022 PDF with pdfplumber probe ([583f175](https://github.com/r3dz4r/datapulse-my/commit/583f1759e233d676522fdd14cbaf60cec64d0c2a))
* **docs:** add Documentation nav dropdown and ship three HTML doc pages ([7873e64](https://github.com/r3dz4r/datapulse-my/commit/7873e6403db72df61b7bc6540a671b23c3d67278))
* **docs:** generalize health-methodology HTML generator to multi-doc manifest ([fdeb6a9](https://github.com/r3dz4r/datapulse-my/commit/fdeb6a99667528b3aa7c3c16656d27ea77ea9664))
* **engine:** add Apache Parquet ingestion for github-hosted MOH data ([5b8c7d6](https://github.com/r3dz4r/datapulse-my/commit/5b8c7d6797948648e52cab938f87d71e00ab9810))
* **register:** drop access-method filter and bucketize recency ([bb0e61d](https://github.com/r3dz4r/datapulse-my/commit/bb0e61d3183177719a5672bd3fae882dbe75816c))
* **register:** remove duplication for a more coherent, legible page ([fe99c5a](https://github.com/r3dz4r/datapulse-my/commit/fe99c5a3df7f8a16d4141d83b5779620f1bfc72b))
* **register:** remove the 'N of total datasets require a real browser' aside note ([4e25593](https://github.com/r3dz4r/datapulse-my/commit/4e255932e3acd42864ac2ea018463066b325ace2))
* **register:** rename Dashboard label to Register, add /register alias, title-copy update ([ad2576d](https://github.com/r3dz4r/datapulse-my/commit/ad2576d7c6c0cb8ef4102184df332b888b9a64a9))
* **register:** semantic tone on observation-status legend (register Slice B) ([2cd9477](https://github.com/r3dz4r/datapulse-my/commit/2cd94770fd7fe6c404b4c1f1ef32d223dbe5aa3b))
* **register:** split muddled Publisher/Category filter + revise payload ceilings ([5a23a3c](https://github.com/r3dz4r/datapulse-my/commit/5a23a3c1d504c1c02d93db9408dc2b8639609758))


### Bug Fixes

* **ci:** align release checks with 412-dataset health ([1e4ea05](https://github.com/r3dz4r/datapulse-my/commit/1e4ea059b4193d3d11c51e5814b83dc61aed62cf))
* **cicd:** deploy root-title check matches the canonical 'DataPulse Dataset Register' ([1084449](https://github.com/r3dz4r/datapulse-my/commit/10844499ef200b77cfddc2f6b6e2fdfa8317d112))
* **cicd:** drop the removed dashboard-browser-facts marker from the release gate configs ([28d5ecb](https://github.com/r3dz4r/datapulse-my/commit/28d5ecb800bf8eb5639e41adcbecda838a941fc4))
* **ci:** persist health-only attestation plane ([81f0de8](https://github.com/r3dz4r/datapulse-my/commit/81f0de8a92cad926dcfaab486e9920a26ee7c352))
* **ci:** refresh chain head before Sigstore sign ([3c23ed8](https://github.com/r3dz4r/datapulse-my/commit/3c23ed8fec41ab50c655039f7287ce8489638c85))
* **ci:** retain hidden attestation files in upload ([fdc54c9](https://github.com/r3dz4r/datapulse-my/commit/fdc54c94e910f33226bf751c3c7ae6a343352c5e))
* **data:** align pricecatcher URL and KKMNOW test ([4e43204](https://github.com/r3dz4r/datapulse-my/commit/4e43204af62b9aee0a94ccab5debd617e62a9723))
* **data:** count multiline ST register CSV records correctly ([bba1bfe](https://github.com/r3dz4r/datapulse-my/commit/bba1bfeb52514035c456153143f7f682d2dd9d5d))
* **data:** probe ST MyEnergyStats through report protocol ([dffa2b1](https://github.com/r3dz4r/datapulse-my/commit/dffa2b1688b78685fa306bea298edabe11381ce0))
* **data:** unify manifest methodology_version to 2 ([a79bb08](https://github.com/r3dz4r/datapulse-my/commit/a79bb0882f4f79aec47befad199485e8755064e7))
* **deploy:** cancel stale health deploys in-progress and parallelise receipt signing ([347ff20](https://github.com/r3dz4r/datapulse-my/commit/347ff2089d32e31febf654a8588eeeb271e9d8a0))
* **mcp:** relax MET-weather freshness guard to accept honest source disposition ([083af97](https://github.com/r3dz4r/datapulse-my/commit/083af976d207119e408fd0e3d6f7ebc985a46e4c))
* **nav:** add chevron affordance + rounded dropdown panel ([bbb73d7](https://github.com/r3dz4r/datapulse-my/commit/bbb73d738805dc1692acbea981e85f807ea4c6bd))
* **register:** hidden filter rows were not visually hidden (display overrode [hidden]) ([2917195](https://github.com/r3dz4r/datapulse-my/commit/2917195e442b580b265099bd2b7c75121686880a))
* **register:** make the register nav self-contained so it renders without the external stylesheet ([627c3fc](https://github.com/r3dz4r/datapulse-my/commit/627c3fc5d8d3e6a7d038e650270645474f257439))
* **verify:** BNM stale-200 guard must not require every documented stale dataset to be stale right now ([d0ea6da](https://github.com/r3dz4r/datapulse-my/commit/d0ea6dab451c4735ed9a8be7f9ffa9667c636685))
* **web:** add a register-coherent documentation article template to datapulse.css ([2d2c32d](https://github.com/r3dz4r/datapulse-my/commit/2d2c32dec2823a5e76c47a794d63d16b2e4e61c8))
* **web:** unify doc-page typography onto the register's Inter theme in datapulse.css ([f7574f9](https://github.com/r3dz4r/datapulse-my/commit/f7574f98d539257dd258726abb9790ba4c1a07dc))

## [0.10.0](https://github.com/r3dz4r/datapulse-my/compare/v0.9.1...v0.10.0) (2026-08-29)


### Features

* **datapulse:** add Learn builder page ([08a0ddd](https://github.com/r3dz4r/datapulse-my/commit/08a0ddd50b0fa6822fa33d326661219e526df8f8))
* **datapulse:** canonicalize public website origin ([8708136](https://github.com/r3dz4r/datapulse-my/commit/87081368e395da6213f325bf1214b248bdea3e3b))
* **datapulse:** canonicalize www origin across source owners ([a2a5e0d](https://github.com/r3dz4r/datapulse-my/commit/a2a5e0d37d60d00f11b4f6c7304ef45360f3e4c0))
* **datapulse:** generate current-origin links and manifest schema ([75260e1](https://github.com/r3dz4r/datapulse-my/commit/75260e15284fe5d041eb12ded0bb8dfa01e8d78f))
* **datapulse:** generate trust verification landing page ([dff2420](https://github.com/r3dz4r/datapulse-my/commit/dff2420c439fe4d008a474c36e0c7a24a1764e83))
* **datapulse:** live evidence receipt and bounded register on landing ([e83f3c7](https://github.com/r3dz4r/datapulse-my/commit/e83f3c7bcae2663039cb295a810d10b1f667931a))
* **openwiki:** deterministic canonical-facts injector + 4 stale pages ([8ab904f](https://github.com/r3dz4r/datapulse-my/commit/8ab904f7145527aefb6a5d3251b96272b068781a))


### Bug Fixes

* **ci:** align served-surface verify with www-canonical routing; color prose to brand ([31253a8](https://github.com/r3dz4r/datapulse-my/commit/31253a8efed064ddab191f35674555d88a1aded3))
* **ci:** include /learn.html in release-invariant pages assertion ([a0bfa72](https://github.com/r3dz4r/datapulse-my/commit/a0bfa72659b0e381ef35e4881771701d43bb27a6))
* **ci:** non-blocking deploy when P6 signer lane is down (artifact_signed:false) ([b241916](https://github.com/r3dz4r/datapulse-my/commit/b241916a8005d6f63c314856b427b1a93e22494b))
* **ci:** preserve release proof across health-only deploys ([3e331b4](https://github.com/r3dz4r/datapulse-my/commit/3e331b45661d677806324b77fdc01779d68360c9))
* **ci:** smoke-test /dashboard surface in post-deploy invariants ([0cd1f70](https://github.com/r3dz4r/datapulse-my/commit/0cd1f70e7967d0aaef4aa305eecfa3638fac9347))
* **ci:** sync-aware post-deploy invariants and dual-plane path filter ([13fbb21](https://github.com/r3dz4r/datapulse-my/commit/13fbb2125a6949725ef65ccefbdfda698c4502c3))
* **ci:** update methodology + deploy-verify gates for shared-template refactor ([324a203](https://github.com/r3dz4r/datapulse-my/commit/324a20352dde1d431ab783dd2bcff4e5108d2f9b))
* **ci:** verify dashboard markers from /dashboard surface ([15ab351](https://github.com/r3dz4r/datapulse-my/commit/15ab351f514b88c6a8e0c5c9172eaadc74c7d472))
* **ci:** wait_synced release proof and legacy format gate ([1b992fc](https://github.com/r3dz4r/datapulse-my/commit/1b992fc9a6774704b50adceb9c3503208f178803))
* **crypto:** derive attestation artifact_signed from rekor witness presence ([d39bec0](https://github.com/r3dz4r/datapulse-my/commit/d39bec0064af22711f5c070cfc0945b574e718e5))
* **datapulse:** add google fonts to landing head and repair catalogue nav anchor ([d2f7fc1](https://github.com/r3dz4r/datapulse-my/commit/d2f7fc1a94a9c7ba5fd50f7e35bd348201f68ada))
* **datapulse:** register Learn page in discovery ([f2c79f2](https://github.com/r3dz4r/datapulse-my/commit/f2c79f2769fb06754cf4231e50853362e89f12d4))
* **datapulse:** remove NPRA Pro Paddle checkout from the public NPRA page ([2a52856](https://github.com/r3dz4r/datapulse-my/commit/2a52856992b8361e8fff30987c40d184770e864f))
* **datapulse:** render health-methodology field list as bullets and restore prose spacing ([9502ec7](https://github.com/r3dz4r/datapulse-my/commit/9502ec7370c472811b77bfbbcff2d89bbf53233f))
* **datapulse:** restore vertical rhythm + section separation in methodology prose ([2b7cc9d](https://github.com/r3dz4r/datapulse-my/commit/2b7cc9de8b94e917fac4ea87af3e3047c8dbfe53))
* **datapulse:** scroll methodology tables horizontally on mobile ([8cc6235](https://github.com/r3dz4r/datapulse-my/commit/8cc62351ea7cb234661bdf120b766886c36e110d))
* **datapulse:** wrap long inline code on mobile in methodology content ([d06ede7](https://github.com/r3dz4r/datapulse-my/commit/d06ede7fcfc75122c97796aed4c5481fc367ba0e))
* **deploy:** preserve Cloudflare trust plane after Pages retirement ([15cd464](https://github.com/r3dz4r/datapulse-my/commit/15cd464d1dc08f6b388545e6ba72340bb7d6dbd6))
* **headers:** use prefix paths and add /assets cache rule ([60d4500](https://github.com/r3dz4r/datapulse-my/commit/60d4500651262d86ee73c6c09fb345d9ddedba49))
* **openwiki:** merge inject and verify into one shell step ([bd13212](https://github.com/r3dz4r/datapulse-my/commit/bd132121c68b78db22b8bdeaec217037a3336e19))
* **openwiki:** neutralize forbidden claims in injector ([cba173d](https://github.com/r3dz4r/datapulse-my/commit/cba173d5605ed118f53e3beb0f29a472043861f5))
* **openwiki:** stop auto-firing on workflow file edits ([ce993e8](https://github.com/r3dz4r/datapulse-my/commit/ce993e84f2c5218399dcee6b4396f11ce1b6c3f0))
* **openwiki:** switch provider from openai-chatgpt (OAuth) to openai (API key) ([ecc84be](https://github.com/r3dz4r/datapulse-my/commit/ecc84bed5dedac27f0b667ef702b4da369affb43))
* **openwiki:** use gpt-5.6-luna (real model) instead of invented gpt-5.6-mini ([6cad556](https://github.com/r3dz4r/datapulse-my/commit/6cad55608b904a859092ec599c304d85ef0f1327))
* remove Google Fonts dependency from all HTML pages ([e744e89](https://github.com/r3dz4r/datapulse-my/commit/e744e89b39e3cbffeca7005805491ff489b627c0))
* **web:** make root the canonical landing route ([a2907a7](https://github.com/r3dz4r/datapulse-my/commit/a2907a794fd571a2a65516ea3a709ed2d71fc2aa))

## [0.9.1](https://github.com/r3dz4r/datapulse-my/compare/v0.9.0...v0.9.1) (2026-08-20)


### Bug Fixes

* **ci:** use github token for anchor attestation ([#20](https://github.com/r3dz4r/datapulse-my/issues/20)) ([83fa749](https://github.com/r3dz4r/datapulse-my/commit/83fa7499845552e7f75939f7f44afafd57f869d1))
* **nginx:** correct MCP vhost hostname ([#19](https://github.com/r3dz4r/datapulse-my/issues/19)) ([1fbe7db](https://github.com/r3dz4r/datapulse-my/commit/1fbe7db4483c1b9c1ebb80c3a703dec6439590ae))

## [0.9.0](https://github.com/r3dz4r/datapulse-my/compare/v0.8.0...v0.9.0) (2026-08-18)


### Features

* **attestation:** publish real Ed25519 key registry + first daily digests ([05081da](https://github.com/r3dz4r/datapulse-my/commit/05081da271dabc632ea3dbb804ca16ea13839f2c))
* **attestation:** signed probe attestation chain + trust_verdict + verify_attestation (the alpha) ([e27b1e8](https://github.com/r3dz4r/datapulse-my/commit/e27b1e82d1bf58c8300f42b53af02e11ad4d816d))
* **drift:** add schema/content drift detection, expose via MCP ([280ddef](https://github.com/r3dz4r/datapulse-my/commit/280ddefaa96b5ca1d0e4a94fc013fe8fa4db2d00))
* **embed:** self-heal changelog-strip in docs/index.html ([d7c9381](https://github.com/r3dz4r/datapulse-my/commit/d7c9381a49151b8925217025502661965dc33a3a))
* **evidence:** evidence receipts + verify_evidence live check — completes trust-layer moat plan ([c01aaf0](https://github.com/r3dz4r/datapulse-my/commit/c01aaf0f88811b27ca7b0176a3f81913eb730a90))
* **generator:** own MCP inventory in llms.txt, README.md, agent.json, docs/mcp-deploy.md ([b39e728](https://github.com/r3dz4r/datapulse-my/commit/b39e728c0a67b06bb2985133dfdd61e92c34a3bc))
* **mcp:** observability foundation — per-buyer JSONL usage sink + usage_summary tool ([4ee851a](https://github.com/r3dz4r/datapulse-my/commit/4ee851a5847ad198179d2cfd8acae2a1edb41900))
* **mcp:** polish tool descriptions and publish score ([79f586c](https://github.com/r3dz4r/datapulse-my/commit/79f586c62e377835b3c027061d1b6475e47e8ec0))
* **methodology:** self-healing page — extract from code, keep prose ([babc03b](https://github.com/r3dz4r/datapulse-my/commit/babc03b9e5c04eeaf18df34e9f409d2ced3c51c9))
* **nav:** self-healing site nav from assets/site-nav.html partial ([8b4877f](https://github.com/r3dz4r/datapulse-my/commit/8b4877fe05602b37eebc391f81f6023a08003cf1))
* **reconciliation:** cross-source duplicate detection + MCP exposure ([2aba9ec](https://github.com/r3dz4r/datapulse-my/commit/2aba9ec869a613c1eaa5b60e7a4310db3e666f4b))
* **reliability:** expose reliability scoring — find_unreliable + min_reliability filter + resource ([9b6b732](https://github.com/r3dz4r/datapulse-my/commit/9b6b7323cad834160962aeaae757524f724f3d6e))
* **scoring:** methodology v2 — missing-signal weighting + reference cap ([be3fcae](https://github.com/r3dz4r/datapulse-my/commit/be3fcae5d38389907358b55694f95a83ae0d0e3c))
* **scoring:** methodology_version 3 with explicit component availability ([57002f1](https://github.com/r3dz4r/datapulse-my/commit/57002f1fcd085203d27185ea786651aaf0ce54c3))
* **theme:** uniform prose typography across all pages ([6b61e1c](https://github.com/r3dz4r/datapulse-my/commit/6b61e1cb915eb324a2771ad0ebacee68a8193a24))


### Bug Fixes

* **ci:** bind DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE secret to deploy step ([d8af2f1](https://github.com/r3dz4r/datapulse-my/commit/d8af2f1871143170963ab4e707c7f7327814e2da))
* **ci:** copy .attestations/ to _site for chain_head.json access ([ada4ca1](https://github.com/r3dz4r/datapulse-my/commit/ada4ca1f16620b1fd268b8d10781b7c47930188c))
* **ci:** deterministic-safety-net green — archives dir + history fixture ([eaab5a6](https://github.com/r3dz4r/datapulse-my/commit/eaab5a608336ea752e6676430eec93869bb486d8))
* **ci:** freshness workflow checks pipeline-liveness, not data freshness ([2c68852](https://github.com/r3dz4r/datapulse-my/commit/2c6885247c3c3daf1af6fcf35e4d3129b42fc07f))
* **ci:** release-please concurrency block — cancel in-flight runs on new push ([aa72932](https://github.com/r3dz4r/datapulse-my/commit/aa72932781fc66ce7d759f868ba89d75c32caa1f))
* **ci:** use GITHUB_TOKEN for attestation anchor injection ([677218e](https://github.com/r3dz4r/datapulse-my/commit/677218e49efe4f7b15748753bb5b6fe99be7b151))
* **ci:** wire DATAPULSE_ARCHIVES_DIR through harness + defensive generate.sh fallback ([36ce9e6](https://github.com/r3dz4r/datapulse-my/commit/36ce9e6d23018454280a0346b444fa91f6c87317))
* **ci:** write the attestation key to a temp file before gen runs ([eaa2cc2](https://github.com/r3dz4r/datapulse-my/commit/eaa2cc2cc83589864958e44a82eeb26a1902fbea))
* **dashboard:** clarify ODIN [#1](https://github.com/r3dz4r/datapulse-my/issues/1) claim with freshness gap framing ([0af9882](https://github.com/r3dz4r/datapulse-my/commit/0af98825022d4e8aec66e790eda821add6dce951))
* **generator:** substitute dataset count in agent.json description ([e85e6c4](https://github.com/r3dz4r/datapulse-my/commit/e85e6c43d0f4ef710a11f8f9d0cd953dcce2d478))
* **health:** audit + reduce 32 unknown-freshness to 0 ([371bf43](https://github.com/r3dz4r/datapulse-my/commit/371bf432d8ac18df3bd5ed7ab4d12e1c5f0f6096))
* **invariants:** include tool annotations in MCP expected_tools ([988f29d](https://github.com/r3dz4r/datapulse-my/commit/988f29db77c2c92d82d9d5624854c588f5b86a20))
* **llms.txt:** correct tool count 15 → 16 in prose paragraph ([d48f3cb](https://github.com/r3dz4r/datapulse-my/commit/d48f3cbfa0a0fb7df3196475feb00d8bf66aed67))
* **mcp:** serialize tool annotations into mcp.json; add PRIVACY.md ([16cfe7b](https://github.com/r3dz4r/datapulse-my/commit/16cfe7b1b83e966130a4738d3834046362bf2853))
* **methodology:** defensive timer read for CI / non-systemd environments ([40fdc81](https://github.com/r3dz4r/datapulse-my/commit/40fdc816f2f81050dc7d645c962a7ef9ecece6a7))
* **methodology:** render with shared datapulse.css + site-nav ([2f1956f](https://github.com/r3dz4r/datapulse-my/commit/2f1956f8b09311a8f169c63a26f6318f3a45390f))
* **migrations:** trim-history single-pass partition (was O(n²)) ([5ad1225](https://github.com/r3dz4r/datapulse-my/commit/5ad1225bad91bc0019718c911ea5b0838728de5a))
* **nav:** eliminate wrapped-row gap between nav links on mobile ([1aa7578](https://github.com/r3dz4r/datapulse-my/commit/1aa75782c91cea85c58dc2fa79f934bc5d5bfa93))
* **telemetry:** add attestation-score to allowed stages ([38bb5dd](https://github.com/r3dz4r/datapulse-my/commit/38bb5dde5bfea27113867ef662fb0617b0356a05))
* **workflow:** suppress Pages deploy on heartbeat-only pushes ([d15dda2](https://github.com/r3dz4r/datapulse-my/commit/d15dda20292479a94ca81db053ac1055f2b88615))

## [0.8.0](https://github.com/r3dz4r/datapulse-my/compare/v0.7.0...v0.8.0) (2026-08-15)


### Features

* **attestation:** publish real Ed25519 key registry + first daily digests ([cf738fd](https://github.com/r3dz4r/datapulse-my/commit/cf738fd506ad20e998011b20d02ef6a22b6676fe))
* **attestation:** signed probe attestation chain + trust_verdict + verify_attestation (the alpha) ([11ec455](https://github.com/r3dz4r/datapulse-my/commit/11ec455b2ca24bce91398159ff1f991aac4cc509))


### Bug Fixes

* **ci:** bind DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE secret to deploy step ([5d60a56](https://github.com/r3dz4r/datapulse-my/commit/5d60a56b8f304b504c6849a393d55fbe2100df25))
* **ci:** copy .attestations/ to _site for chain_head.json access ([a55b3ad](https://github.com/r3dz4r/datapulse-my/commit/a55b3ad0995ced853960529a02f4be93275e74dd))
* **ci:** write the attestation key to a temp file before gen runs ([77f42a7](https://github.com/r3dz4r/datapulse-my/commit/77f42a79b5090a41a0b841cb4b704e7d690ab439))

## [0.7.0](https://github.com/r3dz4r/datapulse-my/compare/v0.6.0...v0.7.0) (2026-08-15)


### Features

* **evidence:** evidence receipts + verify_evidence live check — completes trust-layer moat plan ([8fbc66c](https://github.com/r3dz4r/datapulse-my/commit/8fbc66c9baccb49253dc75e7fe1e150a0251803f))
* **reconciliation:** cross-source duplicate detection + MCP exposure ([b00fd1a](https://github.com/r3dz4r/datapulse-my/commit/b00fd1a0fb669443c4ad36e9b08881e615326b42))
* **reliability:** expose reliability scoring — find_unreliable + min_reliability filter + resource ([105e178](https://github.com/r3dz4r/datapulse-my/commit/105e1786d199d2fc10ccf80153cc1fc22b177989))

## [0.6.0](https://github.com/r3dz4r/datapulse-my/compare/v0.5.0...v0.6.0) (2026-08-15)


### Features

* **anomaly:** calibrate detection — 12/14 rolling tolerance + strict &gt;3x cadence fallback ([e1cfab3](https://github.com/r3dz4r/datapulse-my/commit/e1cfab3fe6e4ea96060aa30e7de7268f67450da6))
* **drift:** add schema/content drift detection, expose via MCP ([859b1bd](https://github.com/r3dz4r/datapulse-my/commit/859b1bd0760f9f063a6ab45e93a15bda1380f048))
* **mcp:** expose anomaly detection — find_anomalies tool + datapulse://anomalies resource ([de3f084](https://github.com/r3dz4r/datapulse-my/commit/de3f084add4e0e3a087edfd5ee208eb3d3fa88c4))
* **trends:** add dataset trend tracking + reliability scoring, expose via MCP ([5706ca6](https://github.com/r3dz4r/datapulse-my/commit/5706ca6a1ed698dc08b0cc1ee35af2972e41763a))


### Bug Fixes

* **docs:** add find_anomalies to llms.txt tool table ([a36ccd9](https://github.com/r3dz4r/datapulse-my/commit/a36ccd97f334415ece0fdc62542938286455d800))

## [0.5.0](https://github.com/r3dz4r/datapulse-my/compare/v0.4.2...v0.5.0) (2026-08-15)


### Features

* **catalogue:** add 4 legal advisory datasets (JBG) to manifest ([fc23623](https://github.com/r3dz4r/datapulse-my/commit/fc23623757b792f70205b2f8bbb86f73a27c057c))
* **catalogue:** generate artifacts for legal_advisory datasets ([a9ad153](https://github.com/r3dz4r/datapulse-my/commit/a9ad1533a10a81f0ad7fd97b34ff3176b668d440))


### Bug Fixes

* **catalogue:** add expected_record_count to legal_advisory entries ([2abe022](https://github.com/r3dz4r/datapulse-my/commit/2abe0228db02996a943b5b2af397b59fd82d4e92))
* **catalogue:** register jbg custodian (Legal Aid Department) ([9481d4c](https://github.com/r3dz4r/datapulse-my/commit/9481d4c540078b687463bf8e652d3be152e7b137))
* **dashboard:** regenerate embedded data + filters for 389 datasets ([4f43b75](https://github.com/r3dz4r/datapulse-my/commit/4f43b75796aa08c5b60b1788a080bf5a91545aa2))
* **mcp:** regenerate mcp.json with 389-dataset descriptions ([5dd028d](https://github.com/r3dz4r/datapulse-my/commit/5dd028d900bb228e57ecd1491a82917d2caf7dbc))

## [0.4.2](https://github.com/r3dz4r/datapulse-my/compare/v0.4.1...v0.4.2) (2026-08-15)


### Bug Fixes

* **mcp:** _fetch_json follows redirects so tools survive DATA_BASE drift ([bf303d7](https://github.com/r3dz4r/datapulse-my/commit/bf303d7792dc8ad4a334d002b523570ecc33bb77))

## 2026-08-06

- Repaired the manifest schema and agent-discovery contracts (`c2aac5c`).
- Wired README summary generation into the 15-minute service source and made
  the summary match the current health snapshot (`606d0bb`).
- Regenerated the JSON-LD catalog with 122 dereferenceable dataset URLs and
  expanded the dashboard graph from 50 to 122 objects (`1b7359b`).
- Regenerated the entry-point and operational documentation from live sources.

## 2026-08-05

- Added dynamic PriceCatcher URLs, CSV/parquet row-count handling, failed-probe
  preservation, and more reliable browser polling.
- Added the README trust-summary generator and initial Pages invariant gate
  (`f618bba`).
- Corrected BNM 1700 freshness handling and made the dashboard display the
  declared MYT publication time (`0dc0712`).

## 2026-08-04

- Added 30 GTFS feeds—16 static and 14 realtime—bringing the catalog to 122
  datasets (`1eb668f`).
- Added namespaces, tiered `--due` probing, JSON-LD, agent discovery files,
  Plausible analytics, and deploy-on-health-workflow completion.
- Distinguished stale data from missing freshness evidence and restored the
  browser-dependent status for browser-only sources.

## 2026-08-03

- Expanded coverage from 13 to 92 datasets across economic, demographic,
  health, utilities, transport, and government-open-data sources.
- Replaced blanket health claims with the eight-status trust taxonomy
  (`0659220`).
- Deployed the read-only MCP service and added adoption issue/PR templates.

## 2026-08-02

- Added the health probe, weekly fallback workflow, badges, RSS feed, samples,
  embedded-data dashboard, GitHub Pages deployment, and agent-ready index.
- Added MET Malaysia, DOE browser-backed sources, iDengue, and initial OpenDOSM
  datasets.

## 2026-08-01

- Added PriceCatcher and four BNM publication-time datasets, growing the
  initial catalog to seven datasets.
- Added the scheduled OpenWiki refresh and corrected the fuel-price schema.

## 2026-07-31

- Created the repository, manifest, contribution model, licence, and the first
  `fuelprice` and `eperolehan-diklankan` health records.
