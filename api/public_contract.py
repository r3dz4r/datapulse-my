"""Public, immutable metadata for the existing buyer API routes.

This deliberately describes only literal route shapes and public query inputs;
it is not an OpenAPI document and it never reads process configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicRoute:
    """One concrete externally reachable buyer API route."""

    method: str
    path: str
    family: str
    query: tuple[str, ...] = ()


PUBLIC_ROUTES: tuple[PublicRoute, ...] = (
    PublicRoute("GET", "/api/v1/health", "health"),
    PublicRoute("GET", "/api/v1/datasets", "datasets", ("limit", "cursor")),
    PublicRoute("GET", "/api/v1/datasets/{id}", "datasets"),
    PublicRoute("GET", "/api/v1/datasets/{id}/history", "dataset-history", ("days", "limit", "cursor")),
    PublicRoute("GET", "/api/v1/deltas", "deltas", ("from", "to", "limit", "cursor")),
    PublicRoute("GET", "/api/v1/deltas/{cycle}", "deltas"),
    PublicRoute("GET", "/api/v1/snapshot", "snapshot"),
    PublicRoute("POST", "/api/v1/paddle/webhook", "paddle"),
    PublicRoute("POST", "/api/v1/paddle/redeem", "paddle"),
    PublicRoute("GET", "/api/v1/keys/me", "keys"),
    PublicRoute("GET", "/api/v1/npra/health", "npra"),
    PublicRoute("GET", "/api/v1/npra/changes", "npra"),
    PublicRoute("GET", "/api/v1/npra/product/{id}", "npra"),
    PublicRoute("GET", "/api/v1/npra/manufacturer/{id}", "npra"),
    PublicRoute("GET", "/api/v1/npra/importer/{id}", "npra"),
)


def public_routes() -> tuple[PublicRoute, ...]:
    """Return the stable, immutable public route registry."""
    return PUBLIC_ROUTES
