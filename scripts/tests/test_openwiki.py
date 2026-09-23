from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.verify_openwiki import VerificationError, find_forbidden_claim, verify


ROOT = Path(__file__).resolve().parents[2]


def _fixture(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "openwiki").mkdir()
    (root / "config/public-surfaces.json").write_text(json.dumps({"schema": "datapulse/v1/public-surfaces", "product_name": "DataPulse", "origins": {"website": "https://www.data-pulse.my", "mcp": "https://mcp.data-pulse.my", "api": "https://api.data-pulse.my", "repository": "https://github.com/r3dz4r/datapulse-my"}, "pages": ["/"], "artifacts": ["/llms.txt"], "featured_dataset_ids": ["alpha"]}), encoding="utf-8")
    (root / "config/public-surfaces.schema.json").write_text(json.dumps({"additionalProperties": False, "properties": {"product_name": {"const": "DataPulse"}, "origins": {"additionalProperties": False, "properties": {"website": {"const": "https://www.data-pulse.my"}, "mcp": {"const": "https://mcp.data-pulse.my"}, "api": {"const": "https://api.data-pulse.my"}, "repository": {"const": "https://github.com/r3dz4r/datapulse-my"}}}}}), encoding="utf-8")
    (root / "datapulse.json").write_text('{"datasets":[{"id":"alpha"}]}', encoding="utf-8")
    (root / "mcp.json").write_text('{"tools":[{"name":"alpha"}]}', encoding="utf-8")
    (root / "openwiki/INSTRUCTIONS.md").write_text("https://www.data-pulse.my\n", encoding="utf-8")
    page = "DataPulse\nhttps://www.data-pulse.my\n1 datasets\n1 read-only tools\n"
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


@pytest.mark.parametrize(
    "stale",
    [
        "DataPulse MY",
        "122 datasets",
        "12 read-only tools",
        "77 datasets",
        "41 read-only tools",
        "999-dataset",
        "77-read-only-tool",
        "16 tools",
        "https://data-pulse.my",
    ],
)
def test_verifier_rejects_stale_current_facts(tmp_path: Path, stale: str) -> None:
    _fixture(tmp_path)
    page = tmp_path / "openwiki/quickstart.md"
    page.write_text(page.read_text(encoding="utf-8") + stale, encoding="utf-8")
    with pytest.raises(VerificationError, match="stale|obsolete"):
        verify(tmp_path, generated=True)


def test_verifier_rejects_a_priced_generated_page(tmp_path: Path) -> None:
    """The withdrawn "USD 25/month" page passed the old literal-only check."""
    _fixture(tmp_path)
    page = tmp_path / "openwiki/quickstart.md"
    page.write_text(
        page.read_text(encoding="utf-8") + "DataPulse costs USD 25 per month for the pro tier.\n",
        encoding="utf-8",
    )
    with pytest.raises(VerificationError, match="unsupported claim") as excinfo:
        verify(tmp_path, generated=True)
    message = str(excinfo.value)
    assert "openwiki/quickstart.md" in message
    assert "USD 25" in message


@pytest.mark.parametrize(
    "claim",
    (
        "A paid tier unlocks faster refreshes.",
        "Billing is handled by Paddle.",
        "Each workspace has a monthly quota.",
        "Use the authenticated /api/v1/ buyer API.",
        "This is a paid product for enterprise accounts.",
    ),
)
def test_verifier_rejects_commercial_and_retired_boundary_claims(
    tmp_path: Path, claim: str
) -> None:
    _fixture(tmp_path)
    page = tmp_path / "openwiki/mcp.md"
    page.write_text(page.read_text(encoding="utf-8") + claim + "\n", encoding="utf-8")
    with pytest.raises(VerificationError, match="unsupported claim"):
        verify(tmp_path, generated=True)


def test_verifier_accepts_honest_negative_commercial_statements(tmp_path: Path) -> None:
    """A page stating that no paid product or authenticated API exists is honest."""
    _fixture(tmp_path)
    page = tmp_path / "openwiki/mcp.md"
    page.write_text(
        page.read_text(encoding="utf-8")
        + "This repository operates no authenticated API and sells no paid product; "
        "it does not charge a monthly fee.\n",
        encoding="utf-8",
    )
    verify(tmp_path, generated=True)


def test_verifier_ignores_the_instruction_prohibition_sentence(tmp_path: Path) -> None:
    """The INSTRUCTIONS.md prohibition wraps across lines and must not be a hit."""
    _fixture(tmp_path)
    prohibition = (
        "Do not claim universal trust, payment capability, reputation,\n"
        "certification, and never state a price, tier, paid quota,\n"
        "billing term, or commercial offer for any product.\n"
    )
    page = tmp_path / "openwiki/operations.md"
    page.write_text(page.read_text(encoding="utf-8") + prohibition, encoding="utf-8")
    verify(tmp_path, generated=True)


def test_matcher_accepts_the_real_instruction_prohibition_line() -> None:
    """The contract's own prohibition names every claim it forbids."""
    text = (ROOT / "openwiki/INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert find_forbidden_claim(text) is None


def test_workflow_uses_locked_local_runtime_and_push_to_main_contract() -> None:
    workflow = (ROOT / ".github/workflows/openwiki-update.yml").read_text(encoding="utf-8")
    assert 'node-version: "22"' in workflow
    assert "npm ci --prefix tools/openwiki" in workflow
    assert "npm install -g" not in workflow
    assert "openwiki code --update --print" in workflow
    assert "OPENWIKI_TELEMETRY_DISABLED" in workflow
    assert "verify_openwiki.py --generated --changed-from HEAD" in workflow
    assert "git push" in workflow
    assert "create-pull-request" not in workflow
    assert "continue-on-error" not in workflow and "|| true" not in workflow
    # OpenWiki is intentionally manual/weekly, never a production-push dependency.
    on_block = workflow.split("on:\n", 1)[1].split("\njobs:", 1)[0]
    assert "push" not in {key.strip() for key in [line.split(":", 1)[0] for line in on_block.splitlines() if ":" in line]}


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
