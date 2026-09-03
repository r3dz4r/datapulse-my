from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import embed_dashboard_data
from scripts.check_url_drift import embedded_manifest


ROOT = Path(__file__).resolve().parents[2]


def _write_public_surface_fixture(root: Path) -> None:
    """Install the strict P5B public-surface contract for an isolated root."""
    config_dir = root / "config"
    config_dir.mkdir(exist_ok=True)
    for name in ("public-surfaces.json", "public-surfaces.schema.json"):
        shutil.copy(ROOT / "config" / name, config_dir / name)


@pytest.fixture(autouse=True)
def public_surface_fixture(tmp_path: Path) -> None:
    _write_public_surface_fixture(tmp_path)


def _strip() -> str:
    return (
        "<!-- BEGIN changelog-strip -->\n"
        "old changelog\n"
        "<!-- END changelog-strip -->\n"
        "<!-- BEGIN dashboard-summary -->\nstale summary\n<!-- END dashboard-summary -->\n"
        "<!-- BEGIN dashboard-trust-facts -->\nstale trust facts\n<!-- END dashboard-trust-facts -->\n"
        "<!-- BEGIN dashboard-browser-facts -->\nstale browser facts\n<!-- END dashboard-browser-facts -->"
    )


def test_attestation_verification_uses_an_isolated_reproducibility_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_verify_contract(root: Path, **kwargs: object) -> dict[str, object]:
        captured["root"] = root
        captured["kwargs"] = kwargs
        return {"freshness": {"status": "current"}}

    monkeypatch.setenv(
        "DATAPULSE_REPRODUCIBILITY_VERIFY_AT", "2026-08-23T10:06:30Z"
    )
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")
    monkeypatch.setattr(embed_dashboard_data, "verify_contract", fake_verify_contract)

    assert embed_dashboard_data._attestation_verification(tmp_path) == {
        "freshness": {"status": "current"}
    }
    assert captured == {
        "root": tmp_path,
        "kwargs": {"now": datetime(2026, 8, 23, 10, 6, 30, tzinfo=timezone.utc)},
    }


def test_attestation_verification_keeps_the_real_time_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_verify_contract(root: Path, **kwargs: object) -> dict[str, object]:
        captured["root"] = root
        captured["kwargs"] = kwargs
        return {"freshness": {"status": "current"}}

    monkeypatch.setenv(
        "DATAPULSE_REPRODUCIBILITY_VERIFY_AT", "2026-08-23T10:06:30Z"
    )
    monkeypatch.delenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", raising=False)
    monkeypatch.setattr(embed_dashboard_data, "verify_contract", fake_verify_contract)

    embed_dashboard_data._attestation_verification(tmp_path)

    assert captured == {"root": tmp_path, "kwargs": {}}


def test_embed_replaces_existing_data_block_with_all_dashboard_inputs(
    tmp_path: Path,
) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text(
        f'<body>{_strip()}<script id="embedded-data">old</script></body>\n',
        encoding="utf-8",
    )
    inputs = {}
    for name, document in {
        "manifest": {"datasets": [{"id": "alpha"}]},
        "health": {
            "checked_at": "2026-08-17T03:30:56Z",
            "datasets": [{"dataset_id": "alpha"}],
            "_trust_summary": {"datasets_total": 1, "by_status": {"browser_dependent": 0}},
        },
        "filters": {"namespaces": [{"key": "all", "count": 1}]},
        "sections": {"generated_at": "now", "sections": [{"key": "other"}]},
    }.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        inputs[name] = path

    embed_dashboard_data.embed(
        html_path,
        inputs["manifest"],
        inputs["health"],
        inputs["filters"],
        inputs["sections"],
    )

    html = html_path.read_text(encoding="utf-8")
    assert html.count('<script id="embedded-data">') == 1
    assert "dashboardFilters:" in html
    assert "dashboardSections:" in html
    assert '"generated_at":"now"' in html
    assert "old" not in html
    assert "2026-08-17</time>; <a href=\"/health/latest.json\">1 datasets tracked" in html


def test_production_homepage_is_the_source_owned_register_with_compatible_payload() -> None:
    """The explicit production path composes register rows with the legacy data API."""
    html = embed_dashboard_data._render_page(
        ROOT / "docs/index.html",
        ROOT / "datapulse.json",
        ROOT / "health/latest.json",
        ROOT / "docs/.dashboard_filters.json",
        ROOT / "docs/.dashboard_sections.json",
        ROOT / "attestations/latest/index.json",
        ROOT / "attestations/latest/binding.json",
        ROOT,
    )
    visible = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL)

    assert "scripts/templates/register-home.html.tmpl" in html
    assert html.count('class="register-row"') == 389
    assert 'class="register-search" id="register-search" type="search" placeholder="Search this register" data-register-search autocomplete="off"' in html
    assert html.count('class="register-chip" data-register-chip') == 5
    assert html.count('data-register-filter=') == 5
    assert 'class="register-chip-label">Status</span>' in html
    assert 'class="register-chip-caret" aria-hidden="true"></span>' in html
    assert 'class="register-count" data-register-count>389 of 389 datasets shown.</span>' in html
    assert 'class="register-clear" data-register-clear data-register-reset hidden>Reset filters</button>' in html
    assert '.register-chip:has(select option:not(:first-child):checked)' in html
    assert '.register-search-row::after' in html
    first_row = re.search(r'<article class="register-row"[^>]*data-posture="([^"]+)"', html)
    assert first_row is not None and first_row.group(1) == "use"
    assert "DataPulse MY" not in html
    assert "DataPulse" in visible
    assert html.count('<script id="embedded-data">') == 1
    assert len(embedded_manifest(html)) == 389
    assert html.index('data-action="official-source"') < html.index('data-action="evidence"') < html.index('data-action="machine-access"')
    for posture in ("use", "warn", "reference-use", "stop"):
        assert f"Decision: {posture}" in html
    assert re.findall(r'<li data-posture="([^"]+)">Decision:', html)[:4] == [
        "use", "warn", "reference-use", "stop"
    ]
    for status in embed_dashboard_data.gen_register_page.STATUS_TO_POSTURE:
        assert f"Status: {status.replace('_', '-')}" in html
    assert "not observed" in html


def test_embed_escapes_script_end_sequences(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text(f"<body>{_strip()}</body>\n", encoding="utf-8")
    paths = []
    documents = [
        {"datasets": [], "value": "</script>"},
        {"checked_at": "2026-08-17T03:30:56Z", "datasets": [], "_trust_summary": {"datasets_total": 0, "by_status": {"browser_dependent": 0}}, "value": "</script>"},
        {"value": "</script>"},
        {"value": "</script>"},
    ]
    for index, document in enumerate(documents):
        path = tmp_path / f"input-{index}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)

    embed_dashboard_data.embed(html_path, *paths)

    html = html_path.read_text(encoding="utf-8")
    assert html.count("</script>") == 1
    assert "<\\/script>" in html


def test_embed_derives_dashboard_dataset_counts_from_trust_summary(
    tmp_path: Path,
) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text(
        f"<body>{_strip()}"
        "We probe 42 official datasets. "
        "<a>42 datasets verified</a>. "
        "Tools over the 42-dataset catalogue."
        "</body>\n",
        encoding="utf-8",
    )
    documents = [
        {"datasets": [{"id": "alpha"}, {"id": "beta"}, {"id": "gamma"}]},
        {
            "checked_at": "2026-08-17T03:30:56Z",
            "datasets": [],
            "_trust_summary": {"datasets_total": 3, "by_status": {"browser_dependent": 0}},
        },
        {"namespaces": []},
        {"sections": []},
    ]
    paths = []
    for index, document in enumerate(documents):
        path = tmp_path / f"input-{index}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)

    embed_dashboard_data.embed(html_path, *paths)

    html = html_path.read_text(encoding="utf-8")
    assert "We probe 42 official datasets" in html
    assert "3 datasets observed" in html
    assert "the 42-dataset catalogue" in html


def test_embed_replaces_inflated_all_dataset_cadence_claims(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text(
        f"<body>{_strip()}We probe 42 official datasets every 5 minutes. "
        "A 5-minute timer fetches each dataset. "
        "Yes — 42 datasets probed every 5 minutes.</body>",
        encoding="utf-8",
    )
    paths = []
    for index, document in enumerate((
        {"datasets": [{"id": "alpha"}]},
        {"checked_at": "2026-08-17T03:30:56Z", "datasets": [], "_trust_summary": {"datasets_total": 1, "by_status": {"browser_dependent": 0}}},
        {},
        {},
    )):
        path = tmp_path / f"cadence-{index}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)

    embed_dashboard_data.embed(html_path, *paths)

    html = html_path.read_text(encoding="utf-8")
    assert "42 official datasets every 5 minutes" in html
    assert "42 datasets probed every 5 minutes" in html
    assert "0 of 1 datasets (0.0%) require a real browser for observation" in html


def test_embed_updates_changelog_strip_idempotently(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text(f"<body>{_strip()}</body>\n", encoding="utf-8")
    documents = [
        {"datasets": [{"id": "alpha"}, {"id": "beta"}]},
        {"checked_at": "2026-08-18T01:02:03+08:00", "datasets": [], "_trust_summary": {"datasets_total": 2, "by_status": {"browser_dependent": 0}}},
        {},
        {},
    ]
    paths = []
    for index, document in enumerate(documents):
        path = tmp_path / f"strip-{index}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)

    embed_dashboard_data.embed(html_path, *paths)
    first = html_path.read_bytes()
    embed_dashboard_data.embed(html_path, *paths)

    html = html_path.read_text(encoding="utf-8")
    assert html_path.read_bytes() == first
    assert html.count(embed_dashboard_data.CHANGELOG_BEGIN) == 1
    assert html.count(embed_dashboard_data.CHANGELOG_END) == 1
    assert '<time datetime="2026-08-17">2026-08-17</time>' in html
    assert "2 datasets tracked" in html
    assert 'href="/health/latest.json"' in html


def test_embed_rejects_missing_changelog_markers(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text("<body></body>\n", encoding="utf-8")
    documents = [
        {"datasets": []},
        {"checked_at": "2026-08-17T03:30:56Z"},
        {},
        {},
    ]
    paths = []
    for index, document in enumerate(documents):
        path = tmp_path / f"missing-{index}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)

    with pytest.raises(embed_dashboard_data.EmbedError, match="exactly one complete"):
        embed_dashboard_data.embed(html_path, *paths)
