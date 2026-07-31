# Contributing to DataPulse MY

Thank you for helping make Malaysian public data easier to trust and reuse.

## Adopt a dataset

Every dataset contribution has three parts:

1. Add an entry to `datapulse.json`.
2. Add a Markdown health report at `data/<dataset-id>.md`.
3. Add a machine-readable JSON envelope at
   `data/json/<dataset-id>.json`.

Use a short, lowercase, hyphen-separated dataset ID. The same ID must appear in
all three places.

### Manifest entry

Every entry in `datapulse.json` must contain:

- `id`
- `name`
- `source`
- `steward`
- `url`
- `licence`
- `attribution`
- `refresh_frequency`
- `geo_coverage`
- `health_report`

### Health report

Describe the dataset's status, freshness, coverage, fields, expected refresh
frequency, collection method, and known quirks. Include a clear licence and
attribution section. State observed facts without implying that DataPulse MY
is the official publisher.

### JSON envelope

Provide the same core facts in valid JSON. At minimum, include the dataset ID,
status, freshness in days, field definitions, known quirks, licence, and
attribution. Add relevant coverage facts such as row count or date range when
they are known.

## Validation rules

Before submitting:

- Confirm `datapulse.json` and the envelope parse as JSON.
- Ensure the dataset ID is unique and matches both report filenames.
- Use ISO 8601 dates in `YYYY-MM-DD` format.
- Represent freshness and row counts as non-negative numbers.
- Use `healthy`, `degraded`, or `unavailable` for status.
- Ensure every manifest `health_report` path exists.
- Keep the Markdown report and JSON envelope factually consistent.
- Do not include credentials, cookies, personal data, or copied source records.
- Check links and reproduce the observations against the official source.

You can validate JSON in PowerShell:

```powershell
Get-Content -Raw datapulse.json | ConvertFrom-Json | Out-Null
Get-Content -Raw data/json/<dataset-id>.json | ConvertFrom-Json | Out-Null
```

## Check the licence

Find the licence statement on the official dataset or publisher site. Record
its exact name and preserve the required attribution. If no licence is stated,
do not assume the data is open: note the uncertainty in the proposed issue or
pull request and ask for review before adding the dataset.

DataPulse MY's MIT licence covers this repository's original work, not the
underlying public datasets.

## Submit a pull request

1. Open an issue describing the dataset and its official source.
2. Fork the repository and create a focused branch.
3. Add the manifest entry, report, and envelope.
4. Run the validation checks and review the rendered Markdown.
5. Commit the three-file contribution with a clear message.
6. Open a pull request that links the issue and explains when and how the
   dataset was checked.

Include evidence for freshness, schema, and licence claims in the pull request
description. Reviewers may ask for a repeat observation when a source is
dynamic or JavaScript-rendered.

## Beginner-friendly issues

Good first contributions include:

- Checking whether a dataset URL still resolves.
- Re-running a freshness observation.
- Correcting typos or broken links in a health report.
- Comparing a JSON envelope with its Markdown report.
- Documenting one reproducible API or browser collection quirk.
- Researching the official licence and attribution for a proposed dataset.
