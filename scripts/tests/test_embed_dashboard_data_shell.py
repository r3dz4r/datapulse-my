from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EMBEDDER = REPOSITORY_ROOT / "scripts/embed_dashboard_data.py"


def _inclusive_head(document: bytes) -> bytes:
    match = re.search(rb"<head>.*?</head>", document, re.DOTALL)
    assert match is not None
    return match.group(0)


def _embedded_block(document: bytes) -> bytes:
    match = re.search(rb"<script id=\"embedded-data\">.*?</script>", document, re.DOTALL)
    assert match is not None
    return match.group(0)


def test_cli_regeneration_preserves_shared_css_shell(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    shutil.copyfile(REPOSITORY_ROOT / "docs/index.html", html_path)

    input_paths: dict[str, Path] = {}
    documents = {
        "manifest": json.loads((REPOSITORY_ROOT / "datapulse.json").read_text()),
        "health": json.loads((REPOSITORY_ROOT / "health/latest.json").read_text()),
        "filters": json.loads(
            (REPOSITORY_ROOT / "docs/.dashboard_filters.json").read_text()
        ),
        "sections": json.loads(
            (REPOSITORY_ROOT / "docs/.dashboard_sections.json").read_text()
        ),
    }
    documents["health"]["checked_at"] = "2026-08-17T00:00:00Z"
    for name, document in documents.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        input_paths[name] = path

    before = html_path.read_bytes()
    subprocess.run(
        [
            sys.executable,
            str(EMBEDDER),
            "--html",
            str(html_path),
            "--manifest",
            str(input_paths["manifest"]),
            "--health",
            str(input_paths["health"]),
            "--filters",
            str(input_paths["filters"]),
            "--sections",
            str(input_paths["sections"]),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    after = html_path.read_bytes()

    before_head = _inclusive_head(before)
    after_head = _inclusive_head(after)
    assert hashlib.sha256(before_head).digest() == hashlib.sha256(after_head).digest()
    assert hashlib.sha256(_embedded_block(before)).digest() != hashlib.sha256(
        _embedded_block(after)
    ).digest()
    assert after_head.count(b'<link rel="stylesheet" href="assets/datapulse.css">') == 1
    assert len(re.findall(rb"<style(?: [^>]*)?>.*?</style>", after_head, re.DOTALL)) == 1
