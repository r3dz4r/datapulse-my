from __future__ import annotations

import json
from pathlib import Path

from scripts import embed_dashboard_data


def test_embed_replaces_existing_data_block_with_all_dashboard_inputs(
    tmp_path: Path,
) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text(
        '<body><script id="embedded-data">old</script></body>\n', encoding="utf-8"
    )
    inputs = {}
    for name, document in {
        "manifest": {"datasets": [{"id": "alpha"}]},
        "health": {"datasets": [{"dataset_id": "alpha"}]},
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


def test_embed_escapes_script_end_sequences(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text("<body></body>\n", encoding="utf-8")
    paths = []
    for index in range(4):
        path = tmp_path / f"input-{index}.json"
        path.write_text(json.dumps({"value": "</script>"}), encoding="utf-8")
        paths.append(path)

    embed_dashboard_data.embed(html_path, *paths)

    html = html_path.read_text(encoding="utf-8")
    assert html.count("</script>") == 1
    assert "<\\/script>" in html
