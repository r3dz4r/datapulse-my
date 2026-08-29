"""Regression tests for release-proof cache synchronization and CI format checks."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"


def _legacy_proof(source_sha: str, verified_at: str) -> str:
    return f"""# Release reproducibility verification

- Verified at: `{verified_at}`
- Source SHA: `{source_sha}`
- Profile result: `bash scripts/generate.sh release-build` exited 0 in both isolated runs
- Total files built: **648**

| Path category | File count | First-run hash | Second-run hash | Match? |
|---|---:|---|---|:---:|
| data/<id>.md | 166 | `first` | `second` | Yes |

## Reproduction

```bash
python3 scripts/verify_release_reproducible.py
```
"""


def _legacy_format_validator() -> str:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["deterministic-safety-net"]["steps"]
    step = next(step for step in steps if step.get("name") == "Validate tracked release-proof legacy format")["run"]
    script = step.split("python3 - docs/release-verification.md <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    return textwrap.dedent(script)


def _validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _legacy_format_validator(), str(path)],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("source_sha", "verified_at"),
    (
        ("b241916a8005d6f63c314856b427b1a93e22494b", "2026-08-29T02:45:57Z"),
        ("042c10f0869a5505e2018d01d1509efd2ef90240", "2026-08-09T11:03:50+08:00"),
    ),
)
def test_ci_legacy_proof_format_accepts_current_and_historical_metadata(
    tmp_path: Path, source_sha: str, verified_at: str
) -> None:
    """The tracked deploy-time proof is format-checked, not freshness-checked."""
    proof = tmp_path / "release-verification.md"
    proof.write_text(_legacy_proof(source_sha, verified_at), encoding="utf-8")

    result = _validate(proof)

    assert result.returncode == 0, result.stderr


def test_ci_legacy_proof_format_rejects_missing_structural_field(tmp_path: Path) -> None:
    """Malformed legacy proof content must fail with an actionable field error."""
    proof = tmp_path / "release-verification.md"
    proof.write_text(
        _legacy_proof("042c10f0869a5505e2018d01d1509efd2ef90240", "2026-08-09T11:03:50+08:00").replace(
            "- Profile result: `bash scripts/generate.sh release-build` exited 0 in both isolated runs\n", ""
        ),
        encoding="utf-8",
    )

    result = _validate(proof)

    assert result.returncode != 0
    assert "Profile result" in result.stderr


def test_deploy_workflow_waits_for_release_proof_cdn_sync() -> None:
    """The post-deploy proof fetch must wait for the Pages CDN cache to refresh."""
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    yaml.safe_load(workflow)

    assert (
        'wait_synced "release-verification.md" release-verification.md '
        '"${website_origin}/release-verification.md" "$smoke_dir/release-verification.md"'
    ) in workflow
    assert 'fetch "release reproducibility proof"' not in workflow
