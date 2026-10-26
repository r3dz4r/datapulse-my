"""Keep producer append merges compatible with publication's main ancestry check."""

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
    pages = yaml.safe_load((ROOT / ".github/workflows/deploy-cloudflare-pages.yml").read_text())
    guard = next(step for step in pages["jobs"]["sign_health"]["steps"]
                 if step.get("id") == "accepted_head")
    assert 'git merge-base --is-ancestor "$PROMOTION_SOURCE_SHA" "$accepted_main"' in guard["run"]
