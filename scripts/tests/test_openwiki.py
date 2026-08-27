from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.verify_openwiki import VerificationError, verify


ROOT = Path(__file__).resolve().parents[2]


def _fixture(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "openwiki").mkdir()
    (root / "config/public-surfaces.json").write_text(json.dumps({"schema": "datapulse/v1/public-surfaces", "origins": {"website": "https://www.data-pulse.my", "mcp": "https://mcp.data-pulse.my", "api": "https://api.data-pulse.my", "repository": "https://github.com/r3dz4r/datapulse-my"}, "pages": ["/"], "artifacts": ["/llms.txt"], "featured_dataset_ids": ["alpha"]}), encoding="utf-8")
    (root / "config/public-surfaces.schema.json").write_text(json.dumps({"additionalProperties": False, "properties": {"origins": {"additionalProperties": False, "properties": {"website": {"const": "https://www.data-pulse.my"}, "mcp": {"const": "https://mcp.data-pulse.my"}, "api": {"const": "https://api.data-pulse.my"}, "repository": {"const": "https://github.com/r3dz4r/datapulse-my"}}}}}), encoding="utf-8")
    (root / "datapulse.json").write_text('{"datasets":[{"id":"alpha"}]}', encoding="utf-8")
    (root / "mcp.json").write_text('{"tools":[{"name":"alpha"}]}', encoding="utf-8")
    (root / "openwiki/INSTRUCTIONS.md").write_text("https://www.data-pulse.my\n", encoding="utf-8")
    page = "https://www.data-pulse.my\n1 datasets\n1 read-only tools\n"
    for name in ("quickstart.md", "datasets.md", "mcp.md", "operations.md"):
        (root / "openwiki" / name).write_text(page, encoding="utf-8")


def test_verifier_accepts_current_canonical_generated_pages(tmp_path: Path) -> None:
    _fixture(tmp_path)
    verify(tmp_path, generated=True)


@pytest.mark.parametrize(
    "command",
    (
        ("python3", "scripts/verify_openwiki.py"),
        ("python3", "-m", "scripts.verify_openwiki"),
    ),
)
def test_source_only_verifier_supports_documented_invocations(command: tuple[str, ...]) -> None:
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )

    assert completed.returncode == 0, completed.stderr
    assert "OpenWiki verification passed" in completed.stdout


@pytest.mark.parametrize("stale", ["122 datasets", "12 read-only tools", "https://data-pulse.my"])
def test_verifier_rejects_stale_current_facts(tmp_path: Path, stale: str) -> None:
    _fixture(tmp_path)
    page = tmp_path / "openwiki/quickstart.md"
    page.write_text(page.read_text(encoding="utf-8") + stale, encoding="utf-8")
    with pytest.raises(VerificationError, match="stale|obsolete"):
        verify(tmp_path, generated=True)


def test_workflow_uses_locked_local_runtime_and_pr_only_contract() -> None:
    workflow = (ROOT / ".github/workflows/openwiki-update.yml").read_text(encoding="utf-8")
    assert 'node-version: "22"' in workflow
    assert "npm ci --prefix tools/openwiki" in workflow
    assert "npm install -g" not in workflow
    assert "openwiki code --update --print" in workflow
    assert "OPENWIKI_TELEMETRY_DISABLED" in workflow
    assert "verify_openwiki.py --generated --changed-from HEAD" in workflow
    assert "peter-evans/create-pull-request" in workflow
    assert "git push" not in workflow
    assert "continue-on-error" not in workflow and "|| true" not in workflow
    assert '"!openwiki/**"' in workflow


def test_normal_ci_runs_source_verifier_without_a_bypass() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    step = workflow.split("      - name: Verify OpenWiki source contract\n", 1)[1]
    assert "run: python3 scripts/verify_openwiki.py" in step
    assert "if:" not in step.split("      - name:", 1)[0]
    assert "continue-on-error" not in step.split("      - name:", 1)[0]


def test_changed_path_allowlist_rejects_source_and_instruction_changes(tmp_path: Path) -> None:
    _fixture(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=test@example.invalid", "-c", "user.name=test", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    (tmp_path / "datapulse.json").write_text('{"datasets":[{"id":"beta"}]}', encoding="utf-8")
    with pytest.raises(VerificationError, match="disallowed"):
        verify(tmp_path, generated=False, changed_from="HEAD")


def test_changed_instruction_file_allows_only_openwiki_marker(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "AGENTS.md").write_text("keep\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=test@example.invalid", "-c", "user.name=test", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    (tmp_path / "AGENTS.md").write_text("keep\n<!-- BEGIN OPENWIKI -->\npointer\n<!-- END OPENWIKI -->\n", encoding="utf-8")
    verify(tmp_path, generated=False, changed_from="HEAD")
    (tmp_path / "AGENTS.md").write_text("changed\n<!-- BEGIN OPENWIKI -->\npointer\n<!-- END OPENWIKI -->\n", encoding="utf-8")
    with pytest.raises(VerificationError, match="non-managed"):
        verify(tmp_path, generated=False, changed_from="HEAD")
