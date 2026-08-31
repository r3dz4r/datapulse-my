"""Regression contract for the preview-only dataset register renderer."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from scripts import gen_register_page
from scripts.public_surface_generation import GenerationError


ROOT = Path(__file__).resolve().parents[2]


def _fixture_root(tmp_path: Path, manifest: list[dict], health: list[dict]) -> Path:
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "scripts/templates").mkdir(parents=True)
    for source, target in (("config/register-page.json", "config/register-page.json"), ("config/register-page.schema.json", "config/register-page.schema.json"), ("config/public-surfaces.json", "config/public-surfaces.json"), ("config/public-surfaces.schema.json", "config/public-surfaces.schema.json"), ("scripts/templates/register.html.tmpl", "scripts/templates/register.html.tmpl"), ("scripts/templates/register.css", "scripts/templates/register.css")):
        (tmp_path / target).write_bytes((ROOT / source).read_bytes())
    (tmp_path / "datapulse.json").write_text(json.dumps({"datasets": manifest}), encoding="utf-8")
    (tmp_path / "health").mkdir()
    (tmp_path / "health/latest.json").write_text(json.dumps({"datasets": health}), encoding="utf-8")
    return tmp_path


def _dataset(dataset_id: str = "alpha", **overrides: object) -> dict:
    return {"id": dataset_id, "name": "Dataset", "source": "Publisher", "namespace": "category", "url": "https://example.test/source", **overrides}


def _health(dataset_id: str = "alpha", status: str = "fresh", **overrides: object) -> dict:
    return {"dataset_id": dataset_id, "status": status, "access_method": "direct", "last_checked": "2026-08-31T00:00:00Z", "content_freshness_date": "2026-08-30", "record_count": 2, **overrides}


def test_valid_config_schema_acceptance() -> None:
    config = gen_register_page._validate_config(ROOT)
    assert config["schema"] == "datapulse/v1/register-page"
    assert config["decision_labels"] == ["use", "warn", "reference-use", "stop"]


def test_legend_styles_are_semantic_and_follow_configured_order() -> None:
    stylesheet = (ROOT / "scripts/templates/register.css").read_text(encoding="utf-8")
    config = json.loads((ROOT / "config/register-page.json").read_text(encoding="utf-8"))
    assert config["decision_labels"] == ["use", "warn", "reference-use", "stop"]
    for posture, token in (
        ("use", "--register-use"),
        ("warn", "--register-warn"),
        ("reference-use", "--register-reference"),
        ("stop", "--register-stop"),
    ):
        assert f'.register-legend li[data-posture="{posture}"]' in stylesheet
        assert f'[data-posture="{posture}"] .register-posture' in stylesheet
        assert token in stylesheet
    assert ".register-legend li:nth-child" not in stylesheet


def test_register_uses_canonical_product_name_only(tmp_path: Path) -> None:
    config = json.loads((ROOT / "config/register-page.json").read_text(encoding="utf-8"))
    copy_fields = tuple(config[field] for field in ("title", "description", "purpose"))
    retired_alias = re.compile(r"\bdatapulse\s+my\b", re.IGNORECASE)

    assert "DataPulse" in config["title"]
    assert all(isinstance(value, str) and not retired_alias.search(value) for value in copy_fields)

    root = _fixture_root(tmp_path, [_dataset()], [_health()])
    rendered = gen_register_page.render(root)
    assert "DataPulse" in rendered
    assert not retired_alias.search(rendered)


def test_malformed_config_is_rejected(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path, [_dataset()], [_health()])
    config = json.loads((root / "config/register-page.json").read_text())
    config["unknown"] = True
    (root / "config/register-page.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(GenerationError, match="Additional properties"):
        gen_register_page.render(root)

    config.pop("unknown")
    config["routes"]["evidence_prefix"] = "/../private/"
    (root / "config/register-page.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(GenerationError, match="/data/"):
        gen_register_page.render(root)


@pytest.mark.parametrize("status,posture", [("fresh", "use"), ("aging", "warn"), ("stale", "stop"), ("discontinued", "stop"), ("degraded", "stop"), ("browser_dependent", "stop"), ("unreachable", "stop"), ("unknown", "stop"), ("unknown_freshness", "stop"), ("reference", "reference-use")])
def test_all_taxonomy_statuses_have_existing_postures(tmp_path: Path, status: str, posture: str) -> None:
    root = _fixture_root(tmp_path, [_dataset()], [_health(status=status)])
    rendered = gen_register_page.render(root)
    assert f'data-posture="{posture}"' in rendered
    assert f"Status: {status.replace('_', '-')}" in rendered


def test_renders_all_fixture_records_and_not_observed_missing_health(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path, [_dataset("alpha"), _dataset("beta")], [_health("alpha", record_count=None)])
    rendered = gen_register_page.render(root)
    assert rendered.count('class="register-row"') == 2
    assert 'data-dataset-id="beta"' in rendered
    assert "Status: not observed" in rendered
    assert rendered.count("not observed") >= 3


def test_posture_first_ordering_uses_recency_then_dataset_id(tmp_path: Path) -> None:
    root = _fixture_root(
        tmp_path,
        [
            _dataset("a-stop"),
            _dataset("b-warn-new"),
            _dataset("c-use-old"),
            _dataset("d-reference"),
            _dataset("e-use-new"),
            _dataset("f-warn-old"),
            _dataset("g-use-missing"),
            _dataset("h-use-new"),
        ],
        [
            _health("a-stop", "stale", content_freshness_date="2026-08-31"),
            _health("b-warn-new", "aging", content_freshness_date="2026-08-30"),
            _health("c-use-old", "fresh", content_freshness_date="2026-08-28"),
            _health("d-reference", "reference", content_freshness_date="2026-08-31"),
            _health("e-use-new", "fresh", content_freshness_date="2026-08-30"),
            _health("f-warn-old", "aging", content_freshness_date="2026-08-29"),
            _health("g-use-missing", "fresh", content_freshness_date=None, last_checked=None),
            _health("h-use-new", "fresh", content_freshness_date="2026-08-30"),
        ],
    )

    rendered = gen_register_page.render(root)
    ordered_ids = re.findall(r'data-dataset-id="([^"]+)"', rendered)

    # Warn rows intentionally precede reference-use rows; both precede stop rows.
    assert ordered_ids == ["e-use-new", "h-use-new", "c-use-old", "g-use-missing", "b-warn-new", "f-warn-old", "d-reference", "a-stop"]


def test_escaping_and_action_order(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path, [_dataset(name='<script>alert(1)</script>', source='A & B', url='https://example.test/?q="x"')], [_health(access_method='<bad>')])
    rendered = gen_register_page.render(root)
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "A &amp; B" in rendered
    assert "q=&quot;x&quot;" in rendered
    assert rendered.index('data-action="official-source"') < rendered.index('data-action="evidence"') < rendered.index('data-action="machine-access"')


@pytest.mark.parametrize("dataset_id", ("../private", "alpha/beta", "alpha\\beta", "%2e%2e"))
def test_rejects_dataset_ids_unsafe_for_evidence_paths(tmp_path: Path, dataset_id: str) -> None:
    root = _fixture_root(tmp_path, [_dataset(dataset_id)], [_health(dataset_id)])
    with pytest.raises(GenerationError, match="single safe dataset-id path segment"):
        gen_register_page.render(root)


def test_deterministic_render_and_caller_controlled_output(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path, [_dataset()], [_health()])
    first = gen_register_page.render(root).encode()
    second = gen_register_page.render(root).encode()
    assert first == second
    output = tmp_path / "preview.html"
    assert not output.exists()
    from unittest.mock import patch
    with patch("sys.argv", ["gen_register_page.py", "--root", str(root), "--out", str(output)]):
        assert gen_register_page.main() == 0
    assert output.read_bytes() == first
    assert not (root / "docs/index.html").exists()
    protected = root / "docs/index.html"
    protected.parent.mkdir()
    with patch("sys.argv", ["gen_register_page.py", "--root", str(root), "--out", str(protected)]):
        assert gen_register_page.main() == 1


def test_preview_inlines_dark_precision_stylesheet_without_production_asset(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path, [_dataset()], [_health()])
    rendered = gen_register_page.render(root)
    stylesheet = (root / "scripts/templates/register.css").read_text(encoding="utf-8")
    assert f"<style>\n{stylesheet}\n  </style>" in rendered
    assert "/assets/datapulse.css" not in rendered
    assert "<link rel=\"stylesheet\"" not in rendered
    assert "<script" not in rendered
    assert "url(" not in stylesheet
    for marker in ("--register-canvas:", "--register-panel:", ".register-controls", ".register-row", '[data-posture="use"]', '[data-posture="warn"]', '[data-posture="stop"]', '[data-posture="reference-use"]', ".register-actions", ".register-row details", ":focus-visible", "@media (max-width: 720px)"):
        assert marker in stylesheet
    assert "width: min(1440px, calc(100% - 1rem));" in stylesheet
    assert "min(100% - 1rem" not in stylesheet
    for selector in (".register-nav, .register-shell", ".register-nav { min-width: 0; flex-wrap: wrap; }", ".register-intro, .register-controls, .register-row", ".register-intro > *, .register-controls > *, .register-row > *, .register-list-header > *, .register-legend > *", ".register-row-footer", ".register-actions", ".compact-facts, .evidence-facts", "h1, h2, h3, .register-intro-note, .register-filter-list label, .register-actions a"):
        assert selector in stylesheet


def test_render_preserves_register_visual_structure(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path, [_dataset()], [_health()])
    rendered = gen_register_page.render(root)
    for marker in ('class="register-shell"', 'class="register-intro"', 'class="register-controls"', 'class="register-legend"', 'class="register-actions"', '<details class="register-evidence">'):
        assert marker in rendered


def test_render_does_not_mutate_slice_zero_inputs() -> None:
    preserved = (
        ROOT / "config/register-page.json",
        ROOT / "config/register-page.schema.json",
        ROOT / "notes/2026-08-31-datapulse-slice-0-contract-inventory.md",
    )
    before = {path: hashlib.sha256(path.read_bytes()).digest() for path in preserved}
    gen_register_page.render(ROOT)
    after = {path: hashlib.sha256(path.read_bytes()).digest() for path in preserved}
    assert after == before


def test_rejects_duplicate_manifest_id_and_malformed_health(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path, [_dataset("alpha"), _dataset("alpha")], [_health()])
    with pytest.raises(GenerationError, match="duplicate dataset id"):
        gen_register_page.render(root)
    root = _fixture_root(tmp_path / "second", [_dataset()], [{"status": "fresh"}])
    with pytest.raises(GenerationError, match="dataset_id"):
        gen_register_page.render(root)


def test_real_repository_smoke_renders_current_manifest() -> None:
    rendered = gen_register_page.render(ROOT)
    assert rendered.count('class="register-row"') == 389
    assert "16 tools" not in rendered
    for forbidden in gen_register_page.FORBIDDEN_CLAIMS:
        assert forbidden not in rendered.lower()
