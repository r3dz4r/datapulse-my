"""Keep the producer merge method and deploy regression floor consistent."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = {
    ROOT / ".github/workflows/attestation-append-merge.yml": 1,
    ROOT / ".github/workflows/deploy-cloudflare-pages.yml": 0,
}
MERGE_METHODS = {"--merge", "--squash", "--rebase"}


def _auto_merge_methods(path: Path) -> list[str]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    methods = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            script = step.get("run", "").replace("\\\n", " ")
            for line in script.splitlines():
                invocation = re.search(r"\bgh\s+pr\s+merge\b", line)
                if invocation is None or line[:invocation.start()].lstrip().startswith(("#", "echo ")):
                    continue
                flags = set(re.findall(r"(?<!\S)--[a-z-]+(?=\s|$)", line[invocation.end():]))
                if "--auto" not in flags:
                    continue
                selected = flags & MERGE_METHODS
                assert len(selected) == 1, f"{path}: auto-merge must select one method: {line}"
                methods.append(selected.pop())
    return methods


def test_append_auto_merge_methods_agree_with_deploy_ancestry_check() -> None:
    observed = {path.name: _auto_merge_methods(path) for path in WORKFLOWS}
    for path, expected_count in WORKFLOWS.items():
        assert len(observed[path.name]) == expected_count, f"{path}: append auto-merge invocation count changed"
    assert all(method != "--squash" for methods in observed.values() for method in methods), observed
    assert set(observed["attestation-append-merge.yml"]) == {"--merge"}, observed
    assert observed["deploy-cloudflare-pages.yml"] == []
    deploy = (ROOT / ".github/workflows/deploy-cloudflare-pages.yml").read_text()
    assert 'git merge-base --is-ancestor "$deployed" "$SELECTED_SHA"' in deploy
    assert "submit_attestation_append.sh" not in deploy
