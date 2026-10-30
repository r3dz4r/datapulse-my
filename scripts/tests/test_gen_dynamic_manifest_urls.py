#!/usr/bin/env python3
"""Tests for skipping unconfirmed dynamic URLs."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from scripts.gen_dynamic_manifest_urls import sync_urls


def _write_inputs(root: Path, manifest: object, policy: object, health: object) -> None:
    for name, datasets in (("datapulse.json", manifest), ("scripts/probe-policy.json", policy), ("health/latest.json", health)):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"datasets": datasets}), encoding="utf-8")


def test_unconfirmed_probe_is_skipped_and_confirmed_probe_updates(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    template = "https://example.test/{YYYY}.csv"
    old_url = "https://example.test/2025.csv"
    new_url = "https://example.test/2026.csv"
    manifest = [{"id": "failed", "url": old_url}, {"id": "confirmed", "url": old_url}]
    policy = {name: {"dynamic-url": {"template": template}} for name in ("failed", "confirmed")}
    health = [
        {"dataset_id": "failed", "request_url": new_url, "url": new_url, "http_status": 503},
        {"dataset_id": "confirmed", "request_url": new_url, "url": new_url, "http_status": 200},
    ]
    _write_inputs(tmp_path, manifest, policy, health)
    with caplog.at_level(logging.WARNING):
        assert sync_urls(tmp_path) == ["confirmed"]
    output = (tmp_path / "datapulse.json").read_bytes()
    assert json.loads(output)["datasets"] == [manifest[0], {"id": "confirmed", "url": new_url}]
    assert "failed: probe did not confirm" in caplog.text
    assert sync_urls(tmp_path) == []
    assert (tmp_path / "datapulse.json").read_bytes() == output


@pytest.mark.parametrize("invalid", ["manifest", "policy", "health"])
def test_malformed_collections_raise(tmp_path: Path, invalid: str) -> None:
    collections = {"manifest": [], "policy": {}, "health": []}
    collections[invalid] = None
    _write_inputs(tmp_path, collections["manifest"], collections["policy"], collections["health"])
    with pytest.raises(ValueError, match="must contain dataset collections"):
        sync_urls(tmp_path)


@pytest.mark.parametrize("problem", ["missing_row", "missing_template", "wrong_url"])
def test_invalid_dataset_is_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture, problem: str) -> None:
    manifest = [{"id": "invalid", "url": "https://example.test/2025.csv"}]
    policy = {"invalid": {"dynamic-url": {"template": "https://example.test/{YYYY}.csv"}}}
    health = [{"dataset_id": "invalid", "request_url": "https://example.test/2026.csv", "url": "https://example.test/2026.csv", "http_status": 200}]
    if problem == "missing_row":
        manifest.clear()
    elif problem == "missing_template":
        policy["invalid"]["dynamic-url"].clear()
    else:
        health[0]["request_url"] = "https://example.test/wrong.csv"
    _write_inputs(tmp_path, manifest, policy, health)
    before = (tmp_path / "datapulse.json").read_bytes()
    with caplog.at_level(logging.WARNING):
        assert sync_urls(tmp_path) == []
    assert (tmp_path / "datapulse.json").read_bytes() == before
    assert "invalid:" in caplog.text
