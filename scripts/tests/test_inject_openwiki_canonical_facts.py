from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.inject_openwiki_canonical_facts import InjectError, inject_canonical_facts

ROOT = Path(__file__).resolve().parents[2]

PAGES = (
    "openwiki/quickstart.md",
    "openwiki/datasets.md",
    "openwiki/mcp.md",
    "openwiki/operations.md",
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _build_fixture(
    root: Path,
    *,
    page_body: str,
    datasets_count: int = 3,
    tools_count: int = 2,
    website: str = "https://www.data-pulse.my",
    write_pages: tuple[str, ...] = PAGES,
    write_random_txt: bool = False,
) -> None:
    """Materialise a minimal but contract-valid repository tree under ``root``.

    Mirrors the shape the existing test_openwiki.py fixture uses: a valid
    ``config/public-surfaces.json`` plus the schema file ``load_public_surfaces``
    requires, a minimal ``datapulse.json``/``mcp.json`` carrying the desired
    array lengths, and the four allowlisted OpenWiki pages.
    """
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "openwiki").mkdir(parents=True, exist_ok=True)
    _write_json(
        root / "config/public-surfaces.json",
        {
            "schema": "datapulse/v1/public-surfaces",
            "origins": {
                "website": website,
                "mcp": "https://mcp.data-pulse.my",
                "api": "https://api.data-pulse.my",
                "repository": "https://github.com/r3dz4r/datapulse-my",
            },
            "pages": ["/"],
            "artifacts": ["/llms.txt"],
            "featured_dataset_ids": ["alpha"],
        },
    )
    _write_json(
        root / "config/public-surfaces.schema.json",
        {
            "additionalProperties": False,
            "properties": {
                "origins": {
                    "additionalProperties": False,
                    "properties": {
                        "website": {"const": website},
                        "mcp": {"const": "https://mcp.data-pulse.my"},
                        "api": {"const": "https://api.data-pulse.my"},
                        "repository": {"const": "https://github.com/r3dz4r/datapulse-my"},
                    },
                }
            },
        },
    )
    datasets = [{"id": f"d{i}"} for i in range(datasets_count)]
    tools = [{"name": f"t{i}"} for i in range(tools_count)]
    _write_json(root / "datapulse.json", {"datasets": datasets})
    _write_json(root / "mcp.json", {"tools": tools})
    for relative in write_pages:
        (root / relative).write_text(page_body, encoding="utf-8")
    if write_random_txt:
        (root / "random.txt").write_text("untouched\n", encoding="utf-8")


def _required_literals(website: str, datasets_count: int, tools_count: int) -> tuple[str, str, str]:
    return website, f"{datasets_count} datasets", f"{tools_count} read-only tools"


def test_inject_adds_all_three_required_literals(tmp_path: Path) -> None:
    _build_fixture(tmp_path, page_body="Just some prose, no canonical facts here.\n")
    results = inject_canonical_facts(tmp_path)

    assert results  # 4 page results, one per allowlisted file
    website_literal, datasets_literal, tools_literal = _required_literals(
        "https://www.data-pulse.my", 3, 2
    )
    for relative, status in results:
        assert status == "injected", f"{relative} should have been rewritten"
        text = (tmp_path / relative).read_text(encoding="utf-8")
        assert website_literal in text, f"{relative} missing website literal"
        assert datasets_literal in text, f"{relative} missing datasets literal"
        assert tools_literal in text, f"{relative} missing tools literal"


def test_inject_is_idempotent(tmp_path: Path) -> None:
    _build_fixture(tmp_path, page_body="Just some prose, no canonical facts here.\n")
    first = inject_canonical_facts(tmp_path)
    snapshot_after_first = {
        relative: (tmp_path / relative).read_text(encoding="utf-8") for relative, _ in first
    }
    second = inject_canonical_facts(tmp_path)

    # Every page that was "injected" on the first pass should be "no change" on
    # the second. If any page reports "injected" twice, idempotency is broken.
    assert all(status == "no change" for _, status in second)
    for relative, _ in first:
        after_second = (tmp_path / relative).read_text(encoding="utf-8")
        assert snapshot_after_first[relative] == after_second, (
            f"{relative} changed between idempotent runs"
        )


def test_inject_replaces_stale_count_literals(tmp_path: Path) -> None:
    body = (
        "Intro paragraph.\n\n"
        "We currently publish **122 datasets** and **12 read-only tools**.\n"
    )
    _build_fixture(
        tmp_path,
        page_body=body,
        datasets_count=389,
        tools_count=16,
    )
    inject_canonical_facts(tmp_path)

    text = (tmp_path / "openwiki/quickstart.md").read_text(encoding="utf-8")
    assert "122 datasets" not in text
    assert "12 read-only tools" not in text
    assert "389 datasets" in text
    assert "16 read-only tools" in text


def test_inject_rewrites_obsolete_apex_host(tmp_path: Path) -> None:
    body = "See the live deployment at https://data-pulse.my/path for details.\n"
    _build_fixture(tmp_path, page_body=body)
    inject_canonical_facts(tmp_path)

    text = (tmp_path / "openwiki/quickstart.md").read_text(encoding="utf-8")
    assert "https://data-pulse.my" not in text
    assert "https://www.data-pulse.my/path" in text


def test_inject_preserves_already_canonical_host(tmp_path: Path) -> None:
    """A URL that already starts with ``www.`` must not be touched."""
    body = "Production lives at https://www.data-pulse.my/quickstart today.\n"
    _build_fixture(tmp_path, page_body=body)
    inject_canonical_facts(tmp_path)

    text = (tmp_path / "openwiki/quickstart.md").read_text(encoding="utf-8")
    # Single canonical host appearance (in the prose + the injected section).
    assert text.count("https://www.data-pulse.my") >= 2  # prose + injected section
    assert "https://data-pulse.my" not in text


def test_inject_does_not_touch_files_outside_allowlist(tmp_path: Path) -> None:
    _build_fixture(
        tmp_path,
        page_body="Some prose.\n",
        write_random_txt=True,
    )
    random_before = (tmp_path / "random.txt").read_text(encoding="utf-8")
    inject_canonical_facts(tmp_path)
    random_after = (tmp_path / "random.txt").read_text(encoding="utf-8")
    assert random_before == random_after


def test_inject_does_not_introduce_forbidden_claims(tmp_path: Path) -> None:
    """The injected section must not contain any verifier-rejected claim."""
    _build_fixture(tmp_path, page_body="Just prose.\n")
    inject_canonical_facts(tmp_path)

    forbidden = (
        "universal trust",
        "payment capability",
        "agent reputation",
        "regulatory certification",
    )
    for relative in PAGES:
        text = (tmp_path / relative).read_text(encoding="utf-8")
        folded = text.casefold()
        for claim in forbidden:
            assert claim not in folded, f"{relative} contains forbidden claim {claim!r}"


def test_inject_rejects_apex_only_website_origin(tmp_path: Path) -> None:
    """Refuse to inject when the canonical website lacks the ``www.` subdomain."""
    _build_fixture(
        tmp_path,
        page_body="Prose.\n",
        website="https://data-pulse.my",
    )
    with pytest.raises(InjectError):
        inject_canonical_facts(tmp_path)
    # Files remain untouched when the guard refuses.
    text = (tmp_path / "openwiki/quickstart.md").read_text(encoding="utf-8")
    assert text == "Prose.\n"


def test_inject_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    body = "We publish 122 datasets today.\n"
    _build_fixture(tmp_path, page_body=body)
    before = (tmp_path / "openwiki/quickstart.md").read_text(encoding="utf-8")
    results = inject_canonical_facts(tmp_path, dry_run=True)
    after = (tmp_path / "openwiki/quickstart.md").read_text(encoding="utf-8")
    assert before == after
    assert any(status == "injected" for _, status in results)


def test_forbidden_claims_are_neutralized() -> None:
    """The model's first pass may emit claims the verifier rejects.
    The injector must scrub them so the verifier stays green regardless
    of what the model wrote. Specifically, 'universal trust' is replaced
    with 'verified evidence' (because DataPulse is not the source of truth,
    only an evidence layer), and the other FORBIDDEN_CLAIMS each get a
    precise factual substitute."""

    from scripts.inject_openwiki_canonical_facts import _neutralize_forbidden_claims

    sample = (
        "# D\n\n"
        "DataPulse provides universal trust for Malaysian data.\n"
        "We have agent reputation as a feature.\n"
        "This is regulatory certification of upstream.\n"
        "Payment capability for premium checks.\n"
        "We are regulatorily certified.\n"
    )
    fixed = _neutralize_forbidden_claims(sample)
    forbidden = (
        "universal trust",
        "payment capability",
        "agent reputation",
        "regulatory certification",
        "regulatorily certified",
    )
    folded = fixed.casefold()
    for claim in forbidden:
        assert claim not in folded, f"forbidden claim not stripped: {claim!r}"
    # Safe substitutes must be present
    assert "verified evidence" in folded
    assert "evidence reference" in folded
    assert "evidence history" in folded
    assert "verification record" in folded
    # Idempotency
    fixed2 = _neutralize_forbidden_claims(fixed)
    assert fixed == fixed2

