from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import embed_dashboard_data


def _strip() -> str:
    return (
        "<!-- BEGIN changelog-strip -->\n"
        "old changelog\n"
        "<!-- END changelog-strip -->"
    )


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
    assert "2026-08-17</time> · 1 datasets tracked" in html


def test_embed_escapes_script_end_sequences(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text(f"<body>{_strip()}</body>\n", encoding="utf-8")
    paths = []
    documents = [
        {"datasets": [], "value": "</script>"},
        {"checked_at": "2026-08-17T03:30:56Z", "value": "</script>"},
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
            "_trust_summary": {"datasets_total": 3, "by_status": {}},
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
    assert "We probe 3 official datasets" in html
    assert "3 datasets verified" in html
    assert "the 3-dataset catalogue" in html
    assert "42" not in html


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
        {"checked_at": "2026-08-17T03:30:56Z", "datasets": []},
        {},
        {},
    )):
        path = tmp_path / f"cadence-{index}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)

    embed_dashboard_data.embed(html_path, *paths)

    html = html_path.read_text(encoding="utf-8")
    assert "42 official datasets every 5 minutes" not in html
    assert "42 datasets probed every 5 minutes" not in html
    assert "probes only datasets due under their tiered cadence" in html


def test_embed_updates_changelog_strip_idempotently(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text(f"<body>{_strip()}</body>\n", encoding="utf-8")
    documents = [
        {"datasets": [{"id": "alpha"}, {"id": "beta"}]},
        {"checked_at": "2026-08-18T01:02:03+08:00"},
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
