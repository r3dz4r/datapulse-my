#!/usr/bin/env python3
"""Publish confirmed dynamic probe URLs in the manifest and its derived surfaces."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)
SURFACE_PATHS = (
    "data/json/{id}.json",
    "data/jsonld/{id}.json",
    "data/passports/{id}.json",
    "docs/datasets/{id}.html",
    "docs/okf/datasets/{id}.md",
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def _matches_template(template: str, observed: str) -> bool:
    pattern = re.escape(template)
    pattern = pattern.replace(re.escape("{YYYY-MM}"), r"\d{4}-(?:0[1-9]|1[0-2])")
    pattern = pattern.replace(re.escape("{YYYY}"), r"\d{4}")
    return re.fullmatch(pattern, observed) is not None


def sync_urls(root: Path) -> list[str]:
    """Use one confirmed health snapshot to update all policy driven URLs."""
    manifest_path = root / "datapulse.json"
    manifest = _read(manifest_path)
    policy = _read(root / "scripts/probe-policy.json").get("datasets", {})
    health = _read(root / "health/latest.json").get("datasets", [])
    rows = manifest.get("datasets", [])
    if not isinstance(policy, dict) or not isinstance(health, list) or not isinstance(rows, list):
        raise ValueError("policy, health, and manifest must contain dataset collections")
    by_id = {row["dataset_id"]: row for row in health if isinstance(row, dict) and isinstance(row.get("dataset_id"), str)}
    manifest_by_id = {row["id"]: row for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)}
    updates: dict[str, str] = {}
    for dataset_id, settings in policy.items():
        if not isinstance(settings, dict) or "dynamic-url" not in settings:
            continue
        template = settings["dynamic-url"].get("template")
        observed = by_id.get(dataset_id, {}).get("request_url")
        reported = by_id.get(dataset_id, {}).get("url")
        status = by_id.get(dataset_id, {}).get("http_status")
        if dataset_id not in manifest_by_id or not isinstance(template, str):
            logger.warning("%s: missing manifest row or dynamic URL template", dataset_id)
            continue
        if not isinstance(observed, str) or not _matches_template(template, observed):
            logger.warning("%s: observed request URL does not match policy template", dataset_id)
            continue
        if reported != observed or type(status) is not int or not 200 <= status < 300:
            logger.warning("%s: probe did not confirm the observed URL with HTTP 2xx", dataset_id)
            continue
        if manifest_by_id[dataset_id].get("url") != observed:
            updates[dataset_id] = observed
    if not updates:
        return []
    for dataset_id, observed in updates.items():
        manifest_by_id[dataset_id]["url"] = observed
    serialized = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    handle, temporary_name = tempfile.mkstemp(prefix=".datapulse.", suffix=".tmp", dir=root)
    try:
        with os.fdopen(handle, "wb") as temporary:
            temporary.write(serialized)
        os.chmod(temporary_name, stat.S_IMODE(manifest_path.stat().st_mode))
        os.replace(temporary_name, manifest_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return sorted(updates)


def stale_surfaces(root: Path) -> list[str]:
    manifest = _read(root / "datapulse.json")["datasets"]
    policy = _read(root / "scripts/probe-policy.json")["datasets"]
    by_id = {row["id"]: row for row in manifest}
    stale = []
    for dataset_id, settings in policy.items():
        if "dynamic-url" not in settings:
            continue
        expected = by_id[dataset_id]["url"]
        paths = (root / template.format(id=dataset_id) for template in SURFACE_PATHS)
        if any(not path.is_file() or expected not in path.read_text(encoding="utf-8") for path in paths):
            stale.append(dataset_id)
    return stale


def regenerate(root: Path, dataset_ids: list[str]) -> None:
    for dataset_id in dataset_ids:
        subprocess.run([sys.executable, "scripts/gen_json_envelope.py", "--force", "--dataset", dataset_id], cwd=root, check=True)
    for script in ("gen_jsonld_catalog.py", "embed_dashboard_data.py", "gen_dataset_passports.py", "gen_dataset_pages.py", "gen_okf_bundle.py"):
        subprocess.run([sys.executable, f"scripts/{script}"], cwd=root, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    changed = sync_urls(root)
    stale = stale_surfaces(root)
    pending = sorted(set(changed) | set(stale))
    if pending:
        regenerate(root, pending)
    print(f"Dynamic URLs: {len(changed)} manifest updates, {len(pending)} surface refreshes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
