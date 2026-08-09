# Data report generator fixture

This self-contained input fixture models two manifest rows and their matching
health/report records. Copy the directory to an empty working directory, copy
`scripts/gen_data_reports.sh` into its `scripts/` directory, and invoke the script
with `health/latest.json` to exercise report refreshes without touching the tracked
workspace.

The reports deliberately contain stale generated sections. The generator owns the
`Status`, `Last checked`, and `File size` level-two sections, while the remaining
frontmatter and Markdown sections are hand-authored fixture content. In particular,
the `next_expected_update` fields model snapshot cadence and the unique
`QUIRK_SENTINEL_TEST_DO_NOT_REMOVE_*` paragraphs make preservation observable.

The manifest is included to keep the scenario representative, although
`gen_data_reports.sh` currently derives its work list solely from
`health/latest.json`. A health row without a matching report is skipped; the script
does not create a new report.
