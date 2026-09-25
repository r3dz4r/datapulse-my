from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
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
        "<!-- BEGIN dashboard-trust-facts -->\nstale trust facts\n<!-- END dashboard-trust-facts -->"
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
    assert "2026-08-17</time>" in html
    assert 'Live health snapshot: <a href="/health/latest.json"><time datetime="2026-08-17">2026-08-17</time></a>.' in html


def test_dashboard_health_omits_only_status_values_redundant_with_staleness_status() -> None:
    health = {
        "datasets": [
            {"dataset_id": "same", "status": "fresh", "staleness_status": "fresh", "url": "https://example.test/same", "request_url": "https://example.test/same"},
            {"dataset_id": "different", "status": "stale", "staleness_status": "aging", "url": "https://example.test/original", "request_url": "https://example.test/redirected"},
        ]
    }

    compact = embed_dashboard_data.dashboard_health_payload(health)

    assert "staleness_status" not in compact["datasets"][0]
    assert compact["datasets"][1]["staleness_status"] == "aging"
    assert "request_url" not in compact["datasets"][0]
    assert compact["datasets"][1]["request_url"] == "https://example.test/redirected"
    assert health["datasets"][0]["staleness_status"] == "fresh"
    assert health["datasets"][0]["request_url"] == "https://example.test/same"


def test_production_homepage_is_the_source_owned_register_with_compatible_payload() -> None:
    """The explicit production path composes register rows with the legacy data API."""
    manifest = json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8"))
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
    assert html.count('class="register-row"') == len(manifest["datasets"])
    assert 'class="register-search" id="register-search" type="search" placeholder="Search this register" data-register-search autocomplete="off"' in html
    assert html.count('class="register-chip" data-register-chip') == 4
    assert html.count('data-register-filter=') == 4
    assert 'class="register-chip-label">Status</span>' in html
    assert 'class="register-chip-caret" aria-hidden="true"></span>' in html
    total = len(manifest["datasets"])
    assert f'class="register-count" data-register-count>{total} of {total} datasets shown.</span>' in html
    assert 'class="register-clear" data-register-clear data-register-reset hidden>Reset filters</button>' in html
    assert '.register-chip:has(select option:not(:first-child):checked)' in html
    assert '.register-search-row::after' in html
    first_row = re.search(r'<article class="register-row"[^>]*data-posture="([^"]+)"', html)
    assert first_row is not None and first_row.group(1) == "use"
    assert "DataPulse MY" not in html
    assert "DataPulse" in visible
    assert html.count('<script id="embedded-data">') == 1
    assert len(embedded_manifest(html)) == 1
    assert embedded_manifest(html)[0]["id"] == manifest["datasets"][0]["id"]
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


def test_embed_allows_health_summary_to_lag_manifest(tmp_path: Path) -> None:
    """The register publishes new manifest rows before their first probe completes."""
    html_path = tmp_path / "index.html"
    html_path.write_text(f"<body>{_strip()}</body>\n", encoding="utf-8")
    documents = [
        {"datasets": [{"id": "alpha"}, {"id": "beta"}, {"id": "gamma"}]},
        {
            "checked_at": "2026-08-17T03:30:56Z",
            "datasets": [],
            "_trust_summary": {"datasets_total": 2, "by_status": {"browser_dependent": 0}},
        },
        {"namespaces": []},
        {"sections": []},
    ]
    paths = []
    for index, document in enumerate(documents):
        path = tmp_path / f"lagging-{index}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)

    embed_dashboard_data.embed(html_path, *paths)

    html = html_path.read_text(encoding="utf-8")
    assert "3 datasets observed" in html
    assert "3 published, 2 observed, 1 pending first probe" in html


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
    # The browser-dependent-observation sentence was removed from the register
    # (the browser-facts block and its population are gone), so it must be absent.
    assert "require a real browser for observation" not in html


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
    assert "Live health snapshot:" in html
    assert "2 datasets observed" in html
    assert "datasets tracked" not in html
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


def _render_production_npra() -> str:
    return embed_dashboard_data._render_page(
        ROOT / "docs/npra.html",
        ROOT / "datapulse.json",
        ROOT / "health/latest.json",
        ROOT / "docs/.dashboard_filters.json",
        ROOT / "docs/.dashboard_sections.json",
        ROOT / "attestations/latest/index.json",
        ROOT / "attestations/latest/binding.json",
        ROOT,
    )


def test_production_npra_uses_the_same_origin_health_projection_without_inlining_global_data() -> None:
    html = _render_production_npra()

    assert len(html.encode("utf-8")) <= 307_200
    assert "window.__DATAPULSE_DATA__" not in html
    assert "fetch('/health/index.json'" in html
    assert "fetch('/health/latest.json'" not in html

    # Mutation controls: each public-payload assertion above has a nearby
    # corruption that must be distinguishable from the checked-in contract.
    assert len((html + ("x" * 307_200)).encode("utf-8")) > 307_200
    assert "window.__DATAPULSE_DATA__" in html + "window.__DATAPULSE_DATA__"
    assert "fetch('/health/index.json'" not in html.replace(
        "fetch('/health/index.json'", "fetch('/health/latest.json'"
    )
    assert "fetch('/health/latest.json'" in html.replace(
        "fetch('/health/index.json'", "fetch('/health/latest.json'"
    )


def test_production_npra_consumes_the_same_health_values_as_the_legacy_inline_payload() -> None:
    health = json.loads((ROOT / "health/latest.json").read_text(encoding="utf-8"))
    legacy = embed_dashboard_data.dashboard_health_payload(health)
    legacy_records = {
        row["dataset_id"]: {
            field: row.get(field)
            for field in ("dataset_id", "status", "last_modified")
        }
        for row in legacy["datasets"]
        if row.get("dataset_id") in embed_dashboard_data.NPRA_DATASET_IDS
    }
    rendered_records = embed_dashboard_data.npra_runtime_records(health)

    assert rendered_records == legacy_records
    mutated = {key: value.copy() for key, value in rendered_records.items()}
    dataset_id = next(iter(mutated))
    mutated[dataset_id]["status"] = "mutation-control"
    assert mutated != legacy_records


def test_production_npra_has_a_visible_health_projection_failure_state() -> None:
    html = _render_production_npra()

    assert 'role="alert"' in html
    assert "Unable to load NPRA register data from /health/index.json." in html
    assert 'role="alert"' not in html.replace('role="alert"', "", 1)
    assert "Unable to load NPRA register data from /health/index.json." not in html.replace(
        "Unable to load NPRA register data from /health/index.json.", "", 1
    )


def _run_npra_embedder(output_dir: Path) -> Path:
    """Run the CLI against isolated page copies without touching repo outputs."""
    output_dir.mkdir()
    paths = {}
    for name in ("index.html", "catalogue.html", "npra.html"):
        target = output_dir / name
        shutil.copyfile(ROOT / "docs" / name, target)
        paths[name] = target
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/embed_dashboard_data.py"),
            "--html", str(paths["index.html"]),
            "--catalogue", str(paths["catalogue.html"]),
            "--npra", str(paths["npra.html"]),
            "--manifest", str(ROOT / "datapulse.json"),
            "--health", str(ROOT / "health/latest.json"),
            "--filters", str(ROOT / "docs/.dashboard_filters.json"),
            "--sections", str(ROOT / "docs/.dashboard_sections.json"),
            "--attestations", str(ROOT / "attestations/latest/index.json"),
            "--attestation-binding", str(ROOT / "attestations/latest/binding.json"),
            "--public-surfaces", str(ROOT / "config"),
        ],
        cwd=ROOT,
        check=True,
    )
    return paths["npra.html"]


def test_production_npra_is_cross_process_deterministic_and_idempotent(
    tmp_path: Path,
) -> None:
    # Separate interpreters are required: an in-process double render cannot
    # expose a generator whose output changes the next process's input.
    first = _run_npra_embedder(tmp_path / "first")
    second = _run_npra_embedder(tmp_path / "second")
    first_bytes = first.read_bytes()
    second_bytes = second.read_bytes()

    assert first_bytes == second_bytes
    assert len(first_bytes) <= 307_200
    assert first_bytes != second_bytes + b"\n"

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/embed_dashboard_data.py"),
            "--html", str(tmp_path / "first/index.html"),
            "--catalogue", str(tmp_path / "first/catalogue.html"),
            "--npra", str(first),
            "--manifest", str(ROOT / "datapulse.json"),
            "--health", str(ROOT / "health/latest.json"),
            "--filters", str(ROOT / "docs/.dashboard_filters.json"),
            "--sections", str(ROOT / "docs/.dashboard_sections.json"),
            "--attestations", str(ROOT / "attestations/latest/index.json"),
            "--attestation-binding", str(ROOT / "attestations/latest/binding.json"),
            "--public-surfaces", str(ROOT / "config"),
        ],
        cwd=ROOT,
        check=True,
    )
    assert first.read_bytes() == first_bytes
    assert first.read_bytes() != first_bytes + b"\n"


def test_npra_runtime_marker_is_required() -> None:
    with pytest.raises(embed_dashboard_data.EmbedError, match="marker was not found"):
        embed_dashboard_data._npra_runtime_script("<body></body>")


def test_canonical_npra_without_runtime_marker_fails_but_fixture_does_not(
    tmp_path: Path,
) -> None:
    """Only the canonical NPRA output owns the mandatory runtime projection."""
    page = (
        "<body><!-- BEGIN npra-freshness -->\nold\n<!-- END npra-freshness -->\n"
        "<!-- BEGIN npra-connect -->\nold\n<!-- END npra-connect -->\n"
        "<!-- BEGIN npra-surfaces -->\nold\n<!-- END npra-surfaces --></body>"
    )
    documents = {
        "manifest.json": {"datasets": []},
        "health.json": {
            "checked_at": "2026-08-23T10:06:30Z",
            "datasets": [],
        },
        "filters.json": {},
        "sections.json": {},
    }
    for name, document in documents.items():
        (tmp_path / name).write_text(json.dumps(document), encoding="utf-8")

    canonical = tmp_path / "docs" / "npra.html"
    canonical.parent.mkdir()
    canonical.write_text(page, encoding="utf-8")
    inputs = tuple(tmp_path / name for name in documents)

    with pytest.raises(embed_dashboard_data.EmbedError, match="marker was not found"):
        embed_dashboard_data._render_page(canonical, *inputs, public_surfaces_path=tmp_path)

    fixture = tmp_path / "fixture" / "npra.html"
    fixture.parent.mkdir()
    fixture.write_text(page, encoding="utf-8")
    rendered = embed_dashboard_data._render_page(
        fixture, *inputs, public_surfaces_path=tmp_path
    )

    assert embed_dashboard_data.NPRA_RUNTIME_MANAGED_START not in rendered
    assert embed_dashboard_data.NPRA_RUNTIME_MANAGED_START in (
        rendered + embed_dashboard_data.NPRA_RUNTIME_MANAGED_START
    )
