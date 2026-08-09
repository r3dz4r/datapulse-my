import ast
import json
from pathlib import Path

import pytest
import requests


NOTEBOOK_PATH = Path(__file__).parents[2] / "docs" / "trust-layer-notebook.ipynb"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def load_code_cell(index):
    notebook = json.loads(NOTEBOOK_PATH.read_text())
    source = notebook["cells"][index]["source"]
    return "".join(source) if isinstance(source, list) else source


def test_fresh_example_fails_closed_before_fetch(monkeypatch):
    namespace = {
        "fresh_example": "fuelprice",
        "fresh_rec": {
            "status": "stale",
            "request_url": "https://example.test/fuelprice.csv",
        },
        "requests": requests,
    }
    fetch_attempted = False

    def forbidden_fetch(*args, **kwargs):
        nonlocal fetch_attempted
        fetch_attempted = True
        raise AssertionError("stale official data must not be fetched")

    monkeypatch.setattr(requests, "get", forbidden_fetch)

    with pytest.raises(SystemExit, match="BLOCKED: fuelprice status is stale"):
        exec(load_code_cell(6), namespace)

    assert fetch_attempted is False


def test_stale_health_record_raises_fail_closed_error(monkeypatch):
    mocked_health = {
        "_trust_summary": {
            "datasets_total": 1,
            "checked_at": "2026-08-09T12:30:55Z",
            "by_status": {"stale": 1},
        },
        "datasets": [
            {
                "dataset_id": "known_stale_dataset",
                "status": "stale",
                "last_modified": "2020-01-01T00:00:00Z",
                "staleness_days": 2400,
                "request_url": "https://example.test/known-stale.csv",
            }
        ],
    }
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(mocked_health))

    namespace = {}
    exec(load_code_cell(2), namespace)

    cell_tree = ast.parse(load_code_cell(8))
    function_nodes = [node for node in cell_tree.body if isinstance(node, ast.FunctionDef)]
    exec(compile(ast.Module(body=function_nodes, type_ignores=[]), "cell-9", "exec"), namespace)

    with pytest.raises(SystemExit, match="BLOCKED: 'stale' status"):
        namespace["require_current_dataset"](namespace["ds"][0])
