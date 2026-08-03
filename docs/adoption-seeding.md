# Adoption issue seeding

These four issues should be filed manually after the templates and labels have
been reviewed. Do not paste the bracketed label notes into the form fields;
they are reminders for the maintainer to apply the corresponding GitHub labels.

Before filing, create or confirm these repository labels:

| Label | Colour | Purpose |
| --- | --- | --- |
| `good first issue` | yellow | Small, well-scoped work for a new contributor |
| `adopt-a-dataset` | blue | New dataset adoption or an adoption improvement |
| `freshness-check` | blue | Repeat observation of a dataset's freshness |
| `bug` | red | Incorrect project or tooling behaviour |
| `documentation` | blue | Documentation-only improvements |
| `question` | purple | Questions about the data or project |
| `wontfix` | gray | Work that will not be pursued |

## 1. Improve: DOE MyEQMS Marine Water Quality observation gaps

Use the **Add a dataset** form. The marine-water dataset is already present as
`doe_mqims`, so this issue should improve its observation evidence instead of
creating a duplicate.

[label: adopt-a-dataset]

- **Dataset name:** DOE MyEQMS Marine Water Quality (`doe_mqims`) — observation gaps
- **Source URL:** https://eqms.doe.gov.my/MQIMS/main
- **Steward:** Department of Environment Malaysia
- **Licence:** Open Government Licence (Malaysia)
- **Refresh frequency:** monthly
- **Why is it useful?:** The current health report notes that asynchronously loaded MMWQI cells can be empty. Repeat observations would distinguish genuine missing readings from render timing and make the sample more dependable.
- **Source I can already add: GitHub URL:** https://github.com/r3dz4r/datapulse-my/blob/main/data/doe_mqims.md
- **Self-attestation:** checked after re-verifying the portal and licence

## 2. Adopt: Hospital Bed Capacity (KKM)

Use the **Add a dataset** form. DataPulse MY already tracks the annual
`dgm_hospital_beds` series. Frame this as finding a more current operational or
monthly capacity source, not duplicating that annual series. The proposed
monthly cadence must be confirmed against the source before filing.

[label: adopt-a-dataset]

- **Dataset name:** Hospital Bed Capacity (KKM) — current operational capacity
- **Source URL:** https://data.gov.my/data-catalogue/hospital_beds
- **Steward:** Ministry of Health Malaysia (KKM)
- **Licence:** Creative Commons Attribution 4.0
- **Refresh frequency:** monthly
- **Why is it useful?:** A current hospital-capacity series would help communities and health planners monitor changes between the annual snapshots already tracked by DataPulse MY.
- **Source I can already add: GitHub URL:** https://github.com/r3dz4r/datapulse-my/blob/main/data/dgm_hospital_beds.md
- **Self-attestation:** checked only after confirming a live monthly source; the linked catalogue currently describes annual observations

## 3. Re-verify: dosm_cpi_state freshness

Use the **Re-verify dataset freshness** form.

[label: freshness-check]

- **Dataset ID:** `dosm_cpi_state`
- **Last verified date:** 2026-08-02
- **New observed freshness:** Please re-run the CPI-state probe, record the latest observation date and file-update date, and report whether the observed cadence remains monthly.
- **Source URL re-checked:** check this only after requesting both https://storage.dosm.gov.my/cpi/cpi_2d_state.csv and https://storage.dosm.gov.my/cpi/cpi_2d_state.parquet

## 4. Add a good-first-issue: confirm URL resolve for dosm_lfs_year

This is a small, manual verification task. It may be filed with the question
form or directly by a maintainer after blank issues are disabled.

[label: good-first-issue] (maps to the `good first issue` repository label)
[label: freshness-check]

Confirm that both documented source URLs resolve successfully:

- https://storage.dosm.gov.my/labour/lfs_year.csv
- https://storage.dosm.gov.my/labour/lfs_year.parquet

Report the HTTP status, response content type, and check date. If either URL
fails, update `data/dosm_lfs_year.md` and its JSON envelope in a linked pull
request. Do not copy personal data, credentials, cookies, or fabricated sample
records into the report.
