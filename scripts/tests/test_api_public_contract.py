"""The public registry must remain an exact description of handler branches."""

from __future__ import annotations

import ast
from pathlib import Path

from api.config import PAGINATION_DEFAULT, PAGINATION_MAXIMUM, Config
from api.public_contract import public_routes
from scripts.public_surface_generation import load_public_surfaces


ROOT = Path(__file__).resolve().parents[2]


def test_registry_is_unique_and_matches_literal_handler_routes() -> None:
    source = (ROOT / "api/server.py").read_text(encoding="utf-8")
    strings = {
        node.value for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    registered = {(route.method, route.path) for route in public_routes()}
    assert len(registered) == len(public_routes()) == 15
    literal = {"/api/v1/health", "/api/v1/datasets", "/api/v1/deltas", "/api/v1/snapshot", "/api/v1/keys/me", "/api/v1/paddle/webhook", "/api/v1/paddle/redeem"}
    assert literal <= strings
    assert literal <= {route.path for route in public_routes() if "{" not in route.path}
    assert {"health", "changes", "product", "manufacturer", "importer"} <= strings
    assert "/api/v1/datasets/" in strings
    assert "/api/v1/deltas/" in strings
    assert "/api/v1/npra/" in strings
    assert {route.path for route in public_routes() if route.method == "POST"} == {
        "/api/v1/paddle/webhook", "/api/v1/paddle/redeem"
    }


def test_public_pagination_metadata_matches_runtime_bounds() -> None:
    config = Config.from_env(ROOT)
    assert PAGINATION_DEFAULT == 50
    assert config.pagination_max == 200
    assert PAGINATION_MAXIMUM == 1000


def test_cors_origin_contract_matches_public_surfaces_with_legacy_apex() -> None:
    from api.server import ALLOWED_CORS_ORIGINS

    canonical = load_public_surfaces(ROOT)["origins"]["website"]
    # The canonical website origin must be accepted, the bare apex is retained
    # *only* as an explicitly documented legacy client origin, and no other
    # origin may be allowed.
    assert ALLOWED_CORS_ORIGINS == frozenset(
        {canonical, "https://data-pulse.my"}
    )
    source = (ROOT / "api/server.py").read_text(encoding="utf-8")
    assert "legacy client origin" in source
    # Both handler paths share the single constant; no inline origin sets.
    strings = {
        node.value for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "https://data-pulse.my" in strings
    assert "https://www.data-pulse.my" in strings
