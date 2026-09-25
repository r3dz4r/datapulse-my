from __future__ import annotations

import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    (root / "docs").mkdir(parents=True)
    shutil.copy2(ROOT / "docs/_headers", root / "docs/_headers")
    shutil.copy2(ROOT / "docs/_redirects", root / "docs/_redirects")
    shutil.copy2(ROOT / "robots.txt", root / "robots.txt")
    (root / "docs/okf").mkdir()
    shutil.copy2(ROOT / "docs/okf/index.md", root / "docs/okf/index.md")
    return root


def _assert_ard_header(root: Path) -> None:
    headers = (root / "docs/_headers").read_text(encoding="utf-8")
    assert 'Link: </.well-known/ard.json>; rel="ard"' in headers


def _assert_agentmap(root: Path) -> None:
    lines = (root / "robots.txt").read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("Agentmap:") and line.endswith("/.well-known/ard.json") for line in lines)


def _assert_okf_redirect_targets(root: Path) -> None:
    for line in (root / "docs/_redirects").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields and fields[0].startswith("/okf"):
            assert (root / "docs" / fields[1].lstrip("/")).is_file()


def _assert_legacy_redirects(root: Path) -> None:
    redirects = (root / "docs/_redirects").read_text(encoding="utf-8")
    assert "/methodology /health-methodology 301" in redirects
    assert "/trust-contract /trust-contract.md 301" in redirects


def test_discovery_surfaces_pass(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _assert_ard_header(root)
    _assert_agentmap(root)
    _assert_okf_redirect_targets(root)
    _assert_legacy_redirects(root)


@pytest.mark.parametrize(
    ("relative_path", "needle", "replacement", "assertion"),
    [
        ("docs/_headers", 'Link: </.well-known/ard.json>; rel="ard"', "", _assert_ard_header),
        ("robots.txt", "Agentmap:", "", _assert_agentmap),
        ("docs/_redirects", "/okf/ /okf/index.md 301", "/okf/ /okf/missing.md 301", _assert_okf_redirect_targets),
        ("docs/_redirects", "/methodology /health-methodology 301", "", _assert_legacy_redirects),
    ],
)
def test_each_discovery_assertion_rejects_mutation(
    tmp_path: Path,
    relative_path: str,
    needle: str,
    replacement: str,
    assertion: object,
) -> None:
    root = _fixture_root(tmp_path)
    path = root / relative_path
    content = path.read_text(encoding="utf-8")
    assert needle in content
    path.write_text(content.replace(needle, replacement, 1), encoding="utf-8")
    with pytest.raises(AssertionError):
        assertion(root)  # type: ignore[operator]
