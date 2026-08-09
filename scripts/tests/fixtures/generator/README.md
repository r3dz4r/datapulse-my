# Generator test fixtures

Place generator-specific files under
`scripts/tests/fixtures/generator/<name>/`, preserving their repository-relative
paths. For example, a health fixture belongs at
`scripts/tests/fixtures/generator/<name>/health/latest.json`. Keep each fixture to
the smallest valid input that exercises the behavior under test.

## Minimum inputs

| Generator | Minimum copied inputs | Generated outputs |
| --- | --- | --- |
| `gen_changelog.py` | `datapulse.json`, `health/latest.json` | `changelog.json` |
| `gen_data_reports.sh` | `health/latest.json`, plus each matching `data/<dataset_id>.md` to refresh | The copied `data/<dataset_id>.md` files |
| `gen_dashboard_filters.py` | `datapulse.json` | `docs/.dashboard_filters.json` |
| `gen_json_envelope.py` | `datapulse.json`, `health/latest.json`; matching `data/<dataset_id>.md` files are optional inputs for quirks and breaking changes | `data/json/<dataset_id>.json` |
| `gen_jsonld_catalog.py` | `datapulse.json`, `health/latest.json`, `docs/index.html` | `data/jsonld/<dataset_id>.json`, `data/jsonld/catalog.json`, `docs/index.html` |
| `gen_mcp_reference.py` | `datapulse.json`, `mcp.json`, `mcp/server.py`, and an existing `docs/` directory | `mcp.json`, `docs/mcp-reference.md` |
| `gen_badges.sh` | `health/latest.json`, `scripts/gen_status_legend.sh` | `badges/<dataset_id>.svg`, `badges/status-<status>.svg` |
| `gen_readme_summary.sh` | `health/latest.json`, `README.md` containing the trust-summary marker | `README.md` |
| `gen_rss.sh` | `health/latest.json`, `datapulse.json` | `feed.xml` |
| `gen_status_legend.sh` | `health/latest.json` with `_trust_summary.by_status` | `badges/status-<status>.svg` |

`gen_mcp_reference.py` also requires the packages declared by
`mcp/requirements.txt`. The JSON envelope generator may access dataset source URLs
when it needs to infer fields, so use fixture URLs deliberately or pre-create an
output and test its non-forced path.

## Example

The `minimal` fixture contains the two-row manifest copied from the repository
contract fixture. A test can run the real dashboard generator against it while all
writes remain in the returned temporary directory:

```python
from pathlib import Path

from scripts.tests.generator_harness import run_generator


repository = Path(__file__).resolve().parents[2]
fixture = repository / "scripts/tests/fixtures/generator/minimal"
result = run_generator(
    source_root=fixture,
    generator=repository / "scripts/gen_dashboard_filters.py",
    inputs=["datapulse.json"],
    expected_outputs=["docs/.dashboard_filters.json"],
)

assert result.returncode == 0
assert result.outputs["docs/.dashboard_filters.json"] is not None
```

## Python release fixture

`python_release/` expands the existing two-row `alpha`/`beta` fixture with the
manifest fields required by the Python release generators. It is self-contained:

- `datapulse.json` and `health/latest.json` provide matching manifest and health
  rows, fixed timestamps and record counts, and a complete `_trust_summary`.
- `docs/index.html` contains the minimal dashboard JSON-LD graph that
  `gen_jsonld_catalog.py` updates.
- `mcp.json` is the discovery-document seed that `gen_mcp_reference.py` updates.
- `mcp/server.py` is a copy of the repository runtime server so tests can compare
  generated discovery schemas with the declarations used at runtime.

The fixture deliberately contains no `data/jsonld/` outputs. Tests create any
pre-existing per-dataset files explicitly, including obsolete files used to prove
the generator's current preservation policy.

## Shell generators

The `shell` fixture is shared by the badge, status-legend, README-summary, and RSS
tests. It contains the repository-contract fixture's `alpha` and `beta` manifest
rows, matching health rows and `_trust_summary`, a minimal README with the exact
trust-summary replacement marker used by the generator, and an otherwise empty
`badges/` directory. Tests stage a private copy and add the real
`gen_status_legend.sh` dependency when exercising `gen_badges.sh`, so every write
stays outside the tracked checkout.
