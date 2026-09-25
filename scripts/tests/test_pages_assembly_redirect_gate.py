from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
REDIRECTS = REPO_ROOT / "docs/_redirects"
RULE_PATTERN = re.compile(r"grep -qxF '([^']+)' _site/_redirects")


def redirect_rules() -> list[str]:
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    rules = RULE_PATTERN.findall(workflow_text)
    assert rules, "workflow has no whole-line redirect assertions"
    return rules


def redirect_gate_script() -> str:
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in workflow_text.splitlines()
        if "_site/_redirects" in line
        and (line.strip().startswith("test \"$(grep -c") or line.strip().startswith("grep -qxF"))
    ]
    assert lines, "workflow has no redirect assertion block"
    return "set -euo pipefail\n" + "\n".join(lines) + "\n"


def run_gate(redirect_text: str) -> subprocess.CompletedProcess[str]:
    with TemporaryDirectory() as temp_dir:
        site_dir = Path(temp_dir) / "_site"
        site_dir.mkdir()
        (site_dir / "_redirects").write_text(redirect_text, encoding="utf-8")
        return subprocess.run(
            ["bash", "-c", redirect_gate_script()],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            check=False,
        )


def target_exists(target: str, docs_root: Path) -> bool:
    target_path = docs_root / target
    markdown_source = docs_root / f"{target}.md"
    return target_path.is_file() or markdown_source.is_file()


def test_redirect_gate_accepts_real_rules_and_requires_each_rule() -> None:
    rules = redirect_rules()
    real_text = REDIRECTS.read_text(encoding="utf-8")
    result = run_gate(real_text)
    assert result.returncode == 0
    assert len([line for line in real_text.splitlines() if line.strip()]) >= 4

    missing_rule_text = "\n".join(line for line in real_text.splitlines() if line != rules[2]) + "\n"
    assert run_gate(missing_rule_text).returncode != 0

    near_miss_text = real_text.replace(rules[2], "/okf/index.md 301\n")
    assert run_gate(near_miss_text).returncode != 0

    for rule in rules:
        target = rule.split()[1].lstrip("/")
        assert target_exists(target, REPO_ROOT / "docs"), f"missing redirect target: {target}"

    with TemporaryDirectory() as temp_dir:
        docs_copy = Path(temp_dir) / "docs"
        shutil.copytree(REPO_ROOT / "docs", docs_copy)
        (docs_copy / "okf/index.md").unlink()
        assert not target_exists("okf/index.md", docs_copy)
