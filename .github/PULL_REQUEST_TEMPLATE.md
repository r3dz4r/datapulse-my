## Adopt-a-dataset checklist

- [ ] Linked to a tracking issue
- [ ] Manifest entry in `datapulse.json` (with `id`, `name`, `source`, `steward`, `url`, `licence`, `attribution`, `refresh_frequency`, `geo_coverage`, `health_report`)
- [ ] Markdown health report at `data/<dataset-id>.md`
- [ ] JSON envelope at `data/json/<dataset-id>.json`
- [ ] Manifest + envelope parse as valid JSON
- [ ] Sample downloaded from the live source (no fabrication — use a `# SAMPLE:` flag if hand-constructed)
- [ ] Licence + attribution confirmed
- [ ] `bash scripts/check.sh` runs clean for this dataset
- [ ] No secrets, credentials, cookies, or copied personal records

## What changed?

<!-- Briefly describe the dataset or health-metadata change and link the tracking issue. -->

## Verification evidence

<!-- Record the live source URL, observation date, and relevant command output. -->
