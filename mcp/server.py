"""Read-only FastMCP server for the published DataPulse MY catalogue."""

from __future__ import annotations

import os
import re
import json
import base64
import hashlib
import asyncio
import logging
from copy import deepcopy
from asyncio import gather
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import mcp.types as mcp_types
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware import Middleware
from mcp.types import Icon, Implementation as MCPImplementation, ToolAnnotations
from pydantic import Field
from fastmcp.tools import FunctionTool
from typing_extensions import Annotated


# T29 (2026-08-09): source version marker. Set by `scripts/bump_mcp_source_version.py`
# at the start of each release build. The deployed service exposes this via the
# JSON-RPC `initialize` response's `serverInfo.version` field, alongside (or
# replacing) the legacy "v3.4.5" hand-maintained version. The verify script
# reads this field and compares to the current repo HEAD to detect drift.
SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "32dde448f583cc5fbe660bd047f75085dfc5fc43")
SOURCE_COMMIT_DATE = os.getenv("DATAPULSE_MCP_SOURCE_DATE", "2026-08-13")
SOURCE_VERSION_STRING = (
    f"v3.4.5+{SOURCE_COMMIT_SHA[:7]}"
    if SOURCE_COMMIT_SHA != "dev"
    else "v3.4.5-dev"
)

DATA_BASE = os.getenv("DATA_BASE", "https://r3dz4r.github.io/datapulse-my").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8788"))
REQUEST_TIMEOUT_SECONDS = 30.0
VERIFY_CACHE_SECONDS = 600.0
VERIFY_MAX_REDIRECTS = 5
ZERO = "0" * 64
ALLOWED_SOURCE_HOSTS = frozenset(
    {
        "api.bnm.gov.my",
        "api.data.gov.my",
        "eqms.doe.gov.my",
        "hansard.parlimen.gov.my",
        "idengue.mysa.gov.my",
        "storage.data.gov.my",
        "storage.dosm.gov.my",
        "www.eperolehan.gov.my",
    }
)
EVIDENCE_FIELDS = (
    "last_checked", "http_status", "request_url", "access_dependency",
    "access_method", "freshness_signal", "freshness_signal_source",
    "last_modified", "content_freshness_date", "record_count",
    "record_count_estimated", "first_row_hash", "content_shape_changed",
    "column_count", "expected_record_count", "record_count_within_tolerance",
    "staleness_days", "status", "anomaly_detected", "anomaly_detection", "message",
)
COMPACT_EVIDENCE_FIELDS = (
    "last_checked", "http_status", "request_url", "access_dependency",
    "freshness_signal_source", "content_freshness_date", "record_count",
    "first_row_hash", "anomaly_detected", "status",
)
_VERIFY_CACHE: dict[tuple[str, str, str | None], tuple[float, dict[str, Any]]] = {}
_VERIFY_LOCK = asyncio.Lock()
CC_BY_4 = "Creative Commons Attribution 4.0"
OGL_MY = "Open Government Licence (Malaysia)"
LICENCE_ALIASES = {
    "cc by 4.0": CC_BY_4,
    "creative commons attribution 4.0": CC_BY_4,
    "ogl": OGL_MY,
    "open government licence (malaysia)": OGL_MY,
}
LICENCE_URLS = {
    CC_BY_4: "https://creativecommons.org/licenses/by/4.0/",
    OGL_MY: "https://www.data.gov.my/pages/terms-of-use",
}
RELIABILITY_GRADES = ("A", "B", "C", "D", "F")
RELIABILITY_GRADE_RANK = {
    grade: index for index, grade in enumerate(RELIABILITY_GRADES)
}

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)


def _sanitise_tool_arg(value: Any, *, key: str | None = None) -> Any:
    """Bound tool-call values and redact common credential-shaped fields."""
    if key and ("api_key" in key.casefold() or "token" in key.casefold()):
        return "[REDACTED]"
    if isinstance(value, str):
        return value[:200]
    if isinstance(value, dict):
        return {
            str(item_key): _sanitise_tool_arg(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitise_tool_arg(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitise_tool_arg(item) for item in value]
    return value


def _request_client_ip() -> str:
    """Get the client address forwarded by the local reverse proxy."""
    try:
        request = get_http_request()
        return (
            request.headers.get("x-real-ip")
            or request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
            or (request.client.host if request.client else "unknown")
        )
    except RuntimeError:
        return "unknown"


class ToolUsageLoggingMiddleware(Middleware):
    """Log sanitized usage details for actual MCP tool calls only."""

    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        message = context.message
        args = _sanitise_tool_arg(message.arguments or {})
        logger.info(
            "mcp-tool: tool=%s args=%s ip=%s timestamp=%s",
            message.name,
            json.dumps(args, ensure_ascii=False, separators=(",", ":")),
            _request_client_ip(),
            context.timestamp.isoformat(),
        )
        return await call_next(context)


def _manifest_dataset_count(manifest_path: Path | None = None) -> int:
    """Read the published dataset total for use in agent-facing metadata."""
    if manifest_path is None:
        manifest_path = Path(__file__).resolve().parents[1] / "datapulse.json"

    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        response = httpx.get(
            f"{DATA_BASE}/datapulse.json",
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        manifest = response.json()

    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("datapulse.json must contain a datasets array")
    return len(datasets)


DATASET_COUNT = _manifest_dataset_count()
SEARCH_DESCRIPTION = (
    f"Search DataPulse MY's {DATASET_COUNT} Malaysian public datasets by "
    "natural-language query. "
    "Filter by licence (e.g. 'CC BY 4.0', 'Open Government Licence (Malaysia)') or "
    "source ('OpenDOSM', 'data.gov.my', 'MET Malaysia', etc.). Returns ranked "
    "matches: id, title, source, licence, status, score. Use when an agent needs to "
    "find datasets covering a topic, by an agency, or under a specific licence."
)
GET_DATASET_DESCRIPTION = (
    "Return full detail for one dataset id, including its latest health status and "
    "last-verified timestamp, content_freshness_date, and freshness_signal_source "
    "(last_modified, content_parse, or none). Use to fetch the provenance/citation "
    "metadata for a dataset found via search_datasets and distinguish "
    "unknown-freshness from proven stale data."
)
FIND_STALE_DESCRIPTION = (
    "Return datasets whose status is aging, stale, or degraded, plus datasets missing "
    "from the latest health snapshot. Use when an agent needs to know which data has "
    "a freshness or schema-validity risk."
)
FIND_ANOMALIES_DESCRIPTION = (
    "Return datasets flagged by the latest published anomaly detection, ranked by "
    "how far the observed update interval exceeds its threshold. Optionally require "
    "a minimum publish-reliability grade; includes pipeline-computed anomaly and "
    "reliability evidence so agents do not recompute it."
)
FIND_DETERIORATING_DESCRIPTION = (
    "Return datasets whose published freshness trend is deteriorating, ranked by "
    "staleness slope. Optionally require a minimum historical anomaly rate; includes "
    "pipeline-computed trend and reliability evidence so agents do not recompute it."
)
FIND_RECOVERING_DESCRIPTION = (
    "Return datasets whose published freshness trend is recovering, with the fastest "
    "staleness reductions first. Includes pipeline-computed trend and publish-reliability "
    "evidence."
)
FIND_UNRELIABLE_DESCRIPTION = (
    "Return datasets whose evaluated publish-reliability grade is at or below a "
    "threshold, with the worst grades and lowest on-time percentages first. "
    "Reliability measures timeliness of successful freshness observations, not uptime; "
    "sample days are included so agents can judge evidence depth."
)
FIND_SCHEMA_DRIFT_DESCRIPTION = (
    "Return datasets with published structural or record-count drift evidence, "
    "ranked with structural changes first. Optionally require a minimum number "
    "of structural transitions; includes pipeline-computed evidence so agents "
    "do not infer drift from freshness alone."
)
CHECK_RECONCILIATION_DESCRIPTION = (
    "Return the published cross-source reconciliation group for a dataset name or id, "
    "including per-member counts, dates, statuses, tolerances, and contextual deltas. "
    "A discrepancy requires human review and does not prove either source is wrong."
)
GET_PROVENANCE_DESCRIPTION = (
    "Return citation-ready provenance metadata for the listed dataset ids, plus "
    "compact pipeline-published evidence receipts: row probe time, HTTP status, "
    "request URL, access dependency, freshness source, content date, record count, "
    "shape fingerprint, anomaly flag, and status. Use when an agent must cite data "
    "and show the evidence behind the trust claim without recomputing it."
)
GET_EVIDENCE_DESCRIPTION = (
    "Return the complete pipeline-published evidence receipt for one dataset id, "
    "including probe time, transport, access dependency, freshness, record-count, "
    "shape, tolerance, status, and anomaly fields. Use for a deep audit, e.g. "
    "get_evidence('fuelprice'); values are presented without MCP-side recomputation."
)
VERIFY_EVIDENCE_DESCRIPTION = (
    "Perform a rate-limited live streamed GET for one direct-access dataset and "
    "compare transport receipts with the latest published evidence, e.g. "
    "verify_evidence('fuelprice'). Content dates, row counts, and shape fingerprints "
    "remain pipeline-only and are explicitly reported as unverified; results are "
    "ephemeral and never update health artifacts."
)
FIND_BY_LICENCE_DESCRIPTION = (
    "Return all datasets with the given licence, summarised. Use to enumerate what's "
    "available under a specific licence for compliance/reuse scoping."
)
TRUST_VERDICT_DESCRIPTION = (
    "Return the published signed facts, unsigned methodology-versioned trust score, "
    "and existing health/trend/drift/reconciliation evidence for one canonical dataset id, e.g. 'fuelprice'. "
    "This tool does not re-probe or verify the signature; call verify_attestation separately."
)
VERIFY_ATTESTATION_DESCRIPTION = (
    "Verify a published Ed25519 probe attestation by canonical dataset id or safe relative digest reference, "
    "e.g. 'fuelprice' or 'attestations/2026-08-15/fuelprice.json'. L1 checks signature/key validity; "
    "optional L2 replays daily heads to a Git-tag anchor; L3 is provided by verify_evidence."
)

class SourceImplementation(MCPImplementation):
    """Factory type for protocol server information with source markers."""

    def __new__(cls, **values: Any) -> MCPImplementation:
        return MCPImplementation(
            source_commit_sha=SOURCE_COMMIT_SHA,
            source_commit_date=SOURCE_COMMIT_DATE,
            **values,
        )


# The MCP SDK constructs serverInfo internally, so extend the protocol model it uses.
mcp_types.Implementation = SourceImplementation


mcp = FastMCP(
    "DataPulse MY",
    version=SOURCE_VERSION_STRING,
    instructions="Read-only access to DataPulse MY's Malaysian public dataset catalogue.",
    middleware=[ToolUsageLoggingMiddleware()],
)

READ_ONLY_TOOL_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

TOOL_ICONS = [
    Icon(
        src="https://data-pulse.my/badges/status-fresh.svg",
        mimeType="image/svg+xml",
        sizes=["110x20"],
    )
]
TOOL_META = {
    "publisher": "DataPulse MY",
    "publisher_url": "https://data-pulse.my/",
    "version": SOURCE_VERSION_STRING,
    "repository_url": "https://github.com/r3dz4r/datapulse-my",
    "dataset_count": DATASET_COUNT,
}


async def _fetch_json(path: str) -> dict[str, Any]:
    """Fetch one JSON document from the published DataPulse MY site."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(
            f"{DATA_BASE}/{path.lstrip('/')}", follow_redirects=True
        )
        response.raise_for_status()
        return response.json()


async def _load_manifest() -> dict[str, Any]:
    return await _fetch_json("datapulse.json")


async def _load_health() -> dict[str, Any]:
    return await _fetch_json("health/latest.json")


async def _load_trends() -> dict[str, Any]:
    try:
        trends = await _fetch_json("health/trends.json")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise RuntimeError(
                "Published trend artifact is unavailable; retry after the Pages deployment completes"
            ) from exc
        raise
    if trends.get("schema") != "datapulse/v1/dataset-trends" or not isinstance(
        trends.get("datasets"), list
    ):
        raise ValueError("health/trends.json has an unsupported schema")
    return trends


async def _load_drift() -> dict[str, Any]:
    try:
        drift = await _fetch_json("health/drift.json")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise RuntimeError(
                "Published drift artifact is unavailable; retry after the Pages deployment completes"
            ) from exc
        raise
    if drift.get("schema") != "datapulse/v1/dataset-drift" or not isinstance(drift.get("datasets"), list):
        raise ValueError("health/drift.json has an unsupported schema")
    return drift


async def _load_reconciliation() -> dict[str, Any]:
    try:
        reconciliation = await _fetch_json("health/reconciliation.json")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise RuntimeError(
                "Published reconciliation artifact is unavailable; retry after the Pages deployment completes"
            ) from exc
        raise
    if reconciliation.get("schema") != "datapulse/v1/dataset-reconciliation" or not isinstance(
        reconciliation.get("groups"), list
    ):
        raise ValueError("health/reconciliation.json has an unsupported schema")
    return reconciliation


async def _load_attestations() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        index, head, scores = await gather(
            _fetch_json("attestations/latest/index.json"),
            _fetch_json("attestations/latest/chain_head.json"),
            _fetch_json("attestations/latest/scores.json"),
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise RuntimeError("Published attestation artifacts are unavailable; retry after Pages deployment completes") from exc
        raise
    if index.get("schema") != "datapulse/v1/attestation-index" or not isinstance(index.get("attestations"), dict):
        raise ValueError("attestation index has an unsupported schema")
    if head.get("schema") != "datapulse/v1/daily-chain-head-envelope":
        raise ValueError("chain head has an unsupported schema")
    if scores.get("schema") != "datapulse/v1/trust-scores" or not isinstance(scores.get("datasets"), list):
        raise ValueError("trust scores have an unsupported schema")
    return index, head, scores


async def _load_catalogue() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest, health = await gather(_load_manifest(), _load_health())
    return manifest, health


def _health_by_id(health: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["dataset_id"]: item for item in health.get("datasets", [])}


class _LiveVerificationBlocked(ValueError):
    """Raised when a source URL is outside the safe live-verification policy."""


def _project_evidence(
    health_record: dict[str, Any], fields: tuple[str, ...]
) -> dict[str, Any]:
    """Project published evidence fields without deriving new claims."""
    return {field: health_record.get(field) for field in fields}


def _is_browser_dependent(
    entry: dict[str, Any], health_record: dict[str, Any]
) -> bool:
    return (
        health_record.get("access_dependency") == "browser"
        or str(health_record.get("access_method", "")).strip().casefold() == "camofox"
        or "camofox-rendered" in str(entry.get("source", "")).casefold()
    )


def _validated_live_url(value: str) -> str:
    """Allow only reviewed HTTPS source origins and reject embedded credentials."""
    parsed = urlsplit(value)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme.casefold() != "https":
        raise _LiveVerificationBlocked("live verification requires an HTTPS source URL")
    if parsed.username is not None or parsed.password is not None:
        raise _LiveVerificationBlocked("source URL credentials are not allowed")
    try:
        port = parsed.port
    except ValueError as exc:
        raise _LiveVerificationBlocked("source URL has an invalid port") from exc
    if port not in (None, 443):
        raise _LiveVerificationBlocked("source URL must use the default HTTPS port")
    if host not in ALLOWED_SOURCE_HOSTS:
        raise _LiveVerificationBlocked(
            f"source host is not approved for live verification: {host or 'missing'}"
        )
    return value


def _normalise_http_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _fetch_live_receipts(source_url: str) -> dict[str, Any]:
    """Stream a safe GET and return headers without downloading the response body."""
    current_url = _validated_live_url(source_url)
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "User-Agent": "DataPulseMY/1.0 (+https://data-pulse.my/about)",
        },
    ) as client:
        for redirect_count in range(VERIFY_MAX_REDIRECTS + 1):
            request = client.build_request("GET", current_url)
            response = await client.send(request, stream=True)
            try:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        break
                    if redirect_count >= VERIFY_MAX_REDIRECTS:
                        raise _LiveVerificationBlocked(
                            f"source exceeded {VERIFY_MAX_REDIRECTS} redirects"
                        )
                    current_url = _validated_live_url(urljoin(current_url, location))
                    continue
                content_length_value = response.headers.get("content-length")
                try:
                    content_length = int(content_length_value) if content_length_value is not None else None
                except ValueError:
                    content_length = None
                last_modified_raw = response.headers.get("last-modified")
                return {
                    "request_url": source_url,
                    "final_url": str(response.url),
                    "http_status": response.status_code,
                    "last_modified": _normalise_http_date(last_modified_raw),
                    "content_length": content_length,
                }
            finally:
                await response.aclose()
    raise _LiveVerificationBlocked("redirect response did not include a destination")


def _verification_result_base(
    dataset_id: str, source_url: str | None, health_record: dict[str, Any]
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verification_scope": "transport_receipts",
        "ephemeral": True, "cached": False, "cache_age_seconds": 0.0,
        "source_url": source_url,
        "recorded_last_checked": health_record.get("last_checked"),
        "recorded_status": health_record.get("status"),
        "recorded_staleness_days": health_record.get("staleness_days"),
        "recorded_request_url": health_record.get("request_url"),
        "live_request_url": None, "live_final_url": None, "request_url_match": None,
        "recorded_http_status": health_record.get("http_status"), "live_http_status": None,
        "http_status_match": None, "recorded_last_modified": health_record.get("last_modified"),
        "live_last_modified": None, "last_modified_match": None,
        "recorded_content_length": health_record.get("content_length"),
        "live_content_length": None, "content_length_match": None,
        "recorded_content_date": health_record.get("content_freshness_date"),
        "live_content_date": None, "content_date_match": None,
        "recorded_record_count": health_record.get("record_count"),
        "live_record_count": None, "record_count_match": None,
        "recorded_first_row_hash": health_record.get("first_row_hash"),
        "live_first_row_hash": None, "first_row_hash_match": None,
        "unverified_fields": ["content_freshness_date", "record_count", "first_row_hash"],
        "verdict": "not_verifiable", "details": [],
    }


def _cached_verification_result(
    key: tuple[str, str, str | None], now: float
) -> dict[str, Any] | None:
    cached = _VERIFY_CACHE.get(key)
    if cached is None:
        return None
    cached_at, payload = cached
    age = now - cached_at
    if age >= VERIFY_CACHE_SECONDS:
        _VERIFY_CACHE.pop(key, None)
        return None
    result = deepcopy(payload)
    result["cached"] = True
    result["cache_age_seconds"] = round(max(age, 0.0), 3)
    return result


def _canonical_licence(licence: str) -> str:
    value = licence.strip()
    return LICENCE_ALIASES.get(value.casefold(), value)


def _search_score(entry: dict[str, Any], query: str) -> int:
    """Score query terms with title weighted above an optional description."""
    title = entry.get("name", "").casefold()
    description = entry.get("description", "").casefold()
    normalised_query = " ".join(query.casefold().split())
    terms = re.findall(r"[a-z0-9]+", normalised_query)
    score = sum(5 * title.count(term) + description.count(term) for term in terms)
    if normalised_query == " ".join(title.split()):
        score += 100
    elif normalised_query and normalised_query in title:
        score += 15
    return score


@mcp.tool(
    title="Discover Malaysian Public Data",
    description=SEARCH_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
async def search_datasets(
    query: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "Free-text search terms; natural language is allowed, e.g. "
                "'inflation cpi'."
            ),
            examples=["inflation cpi"],
        ),
    ],
    licence: Annotated[
        str | None,
        Field(
            description=(
                "Optional exact licence name or supported alias, e.g. 'CC BY 4.0'."
            ),
            examples=["CC BY 4.0", "Open Government Licence (Malaysia)"],
        ),
    ] = None,
    source: Annotated[
        str | None,
        Field(
            description=(
                "Optional case-insensitive source-name substring, e.g. 'OpenDOSM'."
            ),
            examples=["OpenDOSM", "data.gov.my", "MET Malaysia"],
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=50,
            description="Maximum ranked matches to return; integer from 1 to 50, e.g. 10.",
        ),
    ] = 10,
) -> list[dict[str, Any]]:
    """Rank live manifest matches.

    Known limitation: the current published manifest has no ``description``
    field, so scoring uses titles only until descriptions are published.
    """
    manifest, health = await _load_catalogue()
    health_records = _health_by_id(health)
    requested_licence = _canonical_licence(licence) if licence else None
    requested_source = source.casefold().strip() if source else None
    matches: list[dict[str, Any]] = []

    for entry in manifest.get("datasets", []):
        if requested_licence and entry.get("licence", "").casefold() != requested_licence.casefold():
            continue
        if requested_source and requested_source not in entry.get("source", "").casefold():
            continue
        score = _search_score(entry, query)
        if score == 0:
            continue
        health_record = health_records.get(entry["id"], {})
        matches.append(
            {
                "id": entry["id"],
                "title": entry["name"],
                "source": entry["source"],
                "licence": entry["licence"],
                "status": health_record.get("status", "unknown"),
                "score": score,
            }
        )

    matches.sort(
        key=lambda item: (
            -item["score"],
            0 if item["id"].startswith("gtfs_static_") else 1,
            item["title"],
            item["id"],
        )
    )
    return matches[:limit]


@mcp.tool(
    title="Inspect Dataset Health and Details",
    description=GET_DATASET_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
async def get_dataset(
    dataset_id: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "Canonical dataset identifier, e.g. 'dosm_cpi_state'. See the "
                "registry catalogue for valid IDs."
            ),
            examples=["dosm_cpi_state"],
        ),
    ],
) -> dict[str, Any]:
    """Merge one exact manifest entry with its current health record."""
    manifest, health = await _load_catalogue()
    entry = next(
        (item for item in manifest.get("datasets", []) if item.get("id") == dataset_id),
        None,
    )
    if entry is None:
        raise ValueError(f"Unknown dataset id: {dataset_id}")

    health_record = _health_by_id(health).get(
        dataset_id,
        {
            "dataset_id": dataset_id,
            "status": "unknown",
            "message": "Missing from latest health snapshot",
            "staleness_days": None,
            "access_dependency": "direct",
            "expected_record_count": entry.get("expected_record_count"),
            "content_freshness_date": None,
            "freshness_signal_source": "none",
        },
    )
    content_freshness_date = health_record.get("content_freshness_date")
    freshness_signal_source = health_record.get("freshness_signal_source")
    source_aliases = {
        "last_modified": "last_modified_header",
        "content_parse": "content_date_parse",
    }
    freshness_signal_source = source_aliases.get(
        freshness_signal_source, freshness_signal_source
    )
    if freshness_signal_source not in {
        "last_modified_header",
        "content_date_parse",
        "none",
    }:
        if health_record.get("last_modified"):
            freshness_signal_source = "last_modified_header"
        elif content_freshness_date:
            freshness_signal_source = "content_date_parse"
        else:
            freshness_signal_source = "none"
    return {
        **entry,
        "status": "unknown",
        "staleness_days": None,
        "access_dependency": (
            "browser" if health_record.get("access_method") == "Camofox" else "direct"
        ),
        "expected_record_count": entry.get("expected_record_count"),
        **health_record,
        "content_freshness_date": content_freshness_date,
        "freshness_signal_source": freshness_signal_source,
        "last_verified": health.get("checked_at"),
        "schema_version": health.get("schema"),
    }


def _snapshot_age_seconds(checked_at: str | None) -> int | None:
    if not checked_at:
        return None
    checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    return max(0, int((datetime.now(timezone.utc) - checked).total_seconds()))


async def find_stale(
    max_age_hours: Annotated[
        int,
        Field(
            ge=0,
            description=(
                "Maximum acceptable age of the latest health check in whole hours; "
                "non-negative integer, e.g. 72."
            ),
            examples=[24, 72],
        ),
    ] = 24,
) -> list[dict[str, Any]]:
    """Return datasets with explicit freshness or schema-validity risks."""
    manifest, health = await _load_catalogue()
    health_records = _health_by_id(health)
    age_seconds = _snapshot_age_seconds(health.get("checked_at"))
    snapshot_is_old = age_seconds is None or age_seconds > max_age_hours * 3600
    stale: list[dict[str, Any]] = []

    for entry in manifest.get("datasets", []):
        record = health_records.get(entry["id"])
        if record is None:
            stale.append(
                {
                    "id": entry["id"],
                    "status": "unknown",
                    "message": "Missing from latest health snapshot",
                    "age_seconds": age_seconds,
                    "staleness_days": None,
                    "access_dependency": "direct",
                    "expected_record_count": entry.get("expected_record_count"),
                }
            )
        elif record.get("status") != "reference" and (
            record.get("status") in {"aging", "stale", "degraded"} or snapshot_is_old
        ):
            message = record.get("message", "No health message")
            if snapshot_is_old and record.get("status") not in {"aging", "stale", "degraded"}:
                message = "Latest health snapshot is older than the requested maximum age"
            stale.append(
                {
                    "id": entry["id"],
                    "status": record.get("status", "unknown"),
                    "message": message,
                    "age_seconds": age_seconds,
                    "staleness_days": record.get("staleness_days"),
                    "access_dependency": record.get("access_dependency", "direct"),
                    "expected_record_count": record.get(
                        "expected_record_count", entry.get("expected_record_count")
                    ),
                }
            )
    return stale


_find_stale_tool = FunctionTool.from_function(
    find_stale,
    title="Identify Freshness and Schema Risks",
    description=FIND_STALE_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
_find_stale_tool.parameters.setdefault("required", [])
mcp.add_tool(_find_stale_tool)


def _anomaly_results(
    manifest: dict[str, Any],
    health: dict[str, Any],
    trends: dict[str, Any],
    *,
    mode: str | None = None,
    min_reliability: str | None = None,
) -> list[dict[str, Any]]:
    """Join pipeline-computed anomaly and reliability evidence and rank it."""
    health_records = _health_by_id(health)
    reliability_records = {
        row["dataset_id"]: row
        for row in trends.get("datasets", [])
        if isinstance(row, dict) and isinstance(row.get("dataset_id"), str)
    }
    anomalies: list[dict[str, Any]] = []

    for entry in manifest.get("datasets", []):
        record = health_records.get(entry["id"], {})
        if record.get("anomaly_detected") is not True:
            continue
        evidence = record.get("anomaly_detection") or {}
        if mode is not None and evidence.get("mode") != mode:
            continue
        reliability = reliability_records.get(entry["id"], {})
        grade = reliability.get("reliability_grade")
        if min_reliability is not None and (
            grade not in RELIABILITY_GRADE_RANK
            or RELIABILITY_GRADE_RANK[grade]
            > RELIABILITY_GRADE_RANK[min_reliability]
        ):
            continue
        latest_days = evidence.get("latest_days")
        threshold_days = evidence.get("threshold_days")
        severity_ratio = (
            latest_days / threshold_days
            if isinstance(latest_days, (int, float))
            and isinstance(threshold_days, (int, float))
            and threshold_days > 0
            else 0.0
        )
        anomalies.append(
            {
                "id": entry["id"],
                "title": entry["name"],
                "status": record.get("status", "unknown"),
                "staleness_days": record.get("staleness_days"),
                "mode": evidence.get("mode"),
                "latest_days": latest_days,
                "threshold_days": threshold_days,
                "severity_ratio": severity_ratio,
                "anomaly_detection": evidence,
                "publish_on_time_pct": reliability.get("publish_on_time_pct"),
                "reliability_grade": grade,
                "reliability_sample_days": reliability.get("reliability_sample_days"),
            }
        )

    anomalies.sort(
        key=lambda item: (
            -item["severity_ratio"],
            -(
                item["staleness_days"]
                if item["staleness_days"] is not None
                else -1
            ),
            item["id"],
        )
    )
    return anomalies


async def find_anomalies(
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=200,
            description=(
                "Maximum ranked anomalies to return; integer from 1 to 200, e.g. 50."
            ),
            examples=[10, 50],
        ),
    ] = 50,
    mode: Annotated[
        str | None,
        Field(
            description=(
                "Optional exact detection mode; e.g. 'rolling_14d' or "
                "'cadence_fallback'."
            ),
            examples=["rolling_14d", "cadence_fallback"],
        ),
    ] = None,
    min_reliability: Annotated[
        str | None,
        Field(
            description=(
                "Optional minimum publish-reliability grade; e.g. 'C' keeps A, B, "
                "and C and excludes insufficient data."
            ),
            examples=["A", "C"],
        ),
    ] = None,
) -> list[dict[str, Any]]:
    """Expose anomaly decisions already computed by the health pipeline."""
    valid_modes = {"rolling_14d", "cadence_fallback", "not_evaluated"}
    if mode is not None and mode not in valid_modes:
        raise ValueError(
            "Unknown anomaly mode: "
            f"{mode}. Expected one of: {', '.join(sorted(valid_modes))}"
        )
    if min_reliability is not None:
        min_reliability = min_reliability.strip().upper()
        if min_reliability not in RELIABILITY_GRADE_RANK:
            raise ValueError(
                "Unknown minimum reliability grade: "
                f"{min_reliability}. Expected one of: {', '.join(RELIABILITY_GRADES)}"
            )

    catalogue, trends = await gather(_load_catalogue(), _load_trends())
    manifest, health = catalogue
    return _anomaly_results(
        manifest,
        health,
        trends,
        mode=mode,
        min_reliability=min_reliability,
    )[:limit]


_find_anomalies_tool = FunctionTool.from_function(
    find_anomalies,
    title="Identify Dataset Update Anomalies",
    description=FIND_ANOMALIES_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
_find_anomalies_tool.parameters.setdefault("required", [])
mcp.add_tool(_find_anomalies_tool)


def _trend_results(
    manifest: dict[str, Any],
    trends: dict[str, Any],
    *,
    trend: str,
    min_anomaly_rate: float | None = None,
) -> list[dict[str, Any]]:
    manifest_by_id = {entry["id"]: entry for entry in manifest.get("datasets", [])}
    results: list[dict[str, Any]] = []
    for row in trends.get("datasets", []):
        entry = manifest_by_id.get(row.get("dataset_id"))
        if entry is None or row.get("trend") != trend:
            continue
        anomaly_rate = row.get("anomaly_rate_pct")
        if min_anomaly_rate is not None and (
            not isinstance(anomaly_rate, (int, float))
            or isinstance(anomaly_rate, bool)
            or anomaly_rate < min_anomaly_rate
        ):
            continue
        results.append(
            {
                "id": entry["id"],
                "title": entry["name"],
                "trend": row["trend"],
                "latest_status": row.get("latest_status"),
                "cadence_days": row.get("cadence_days"),
                "latest_staleness_days": row.get("latest_staleness_days"),
                "slope_days_per_week": row.get("slope_days_per_week"),
                "trend_sample_days": row.get("trend_sample_days"),
                "history_span_days": row.get("history_span_days"),
                "publish_on_time_pct": row.get("publish_on_time_pct"),
                "reliability_grade": row.get("reliability_grade"),
                "reliability_sample_days": row.get("reliability_sample_days"),
                "anomaly_rate_pct": anomaly_rate,
                "anomaly_sample_days": row.get("anomaly_sample_days"),
                "reason": row.get("reason"),
            }
        )
    if trend == "deteriorating":
        results.sort(
            key=lambda item: (
                -item["slope_days_per_week"]
                if isinstance(item["slope_days_per_week"], (int, float))
                else float("inf"),
                -(item["anomaly_rate_pct"] if isinstance(item["anomaly_rate_pct"], (int, float)) else -1),
                item["publish_on_time_pct"] if isinstance(item["publish_on_time_pct"], (int, float)) else 101,
                item["id"],
            )
        )
    else:
        results.sort(
            key=lambda item: (
                item["slope_days_per_week"] if isinstance(item["slope_days_per_week"], (int, float)) else float("inf"),
                item["id"],
            )
        )
    return results


async def find_deteriorating(
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=200,
            description="Maximum ranked deteriorating datasets to return; integer from 1 to 200, e.g. 50.",
            examples=[10, 50],
        ),
    ] = 50,
    min_anomaly_rate: Annotated[
        float | None,
        Field(
            ge=0,
            le=100,
            description="Optional minimum percent of anomaly-evaluable history days, e.g. 25.0.",
            examples=[25.0, 50.0],
        ),
    ] = None,
) -> list[dict[str, Any]]:
    """Expose pipeline-computed deteriorating trend decisions."""
    manifest, trends = await gather(_load_manifest(), _load_trends())
    return _trend_results(
        manifest, trends, trend="deteriorating", min_anomaly_rate=min_anomaly_rate
    )[:limit]


_find_deteriorating_tool = FunctionTool.from_function(
    find_deteriorating,
    title="Identify Deteriorating Dataset Trends",
    description=FIND_DETERIORATING_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
_find_deteriorating_tool.parameters.setdefault("required", [])
mcp.add_tool(_find_deteriorating_tool)


async def find_recovering(
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=200,
            description="Maximum ranked recovering datasets to return; integer from 1 to 200, e.g. 50.",
            examples=[10, 50],
        ),
    ] = 50,
) -> list[dict[str, Any]]:
    """Expose pipeline-computed recovering trend decisions."""
    manifest, trends = await gather(_load_manifest(), _load_trends())
    return _trend_results(manifest, trends, trend="recovering")[:limit]


_find_recovering_tool = FunctionTool.from_function(
    find_recovering,
    title="Identify Recovering Dataset Trends",
    description=FIND_RECOVERING_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
_find_recovering_tool.parameters.setdefault("required", [])
mcp.add_tool(_find_recovering_tool)


def _unreliable_results(
    manifest: dict[str, Any],
    trends: dict[str, Any],
    *,
    at_or_below_grade: str,
) -> list[dict[str, Any]]:
    """Join evaluated reliability evidence to manifest titles and rank it."""
    manifest_by_id = {entry["id"]: entry for entry in manifest.get("datasets", [])}
    threshold_rank = RELIABILITY_GRADE_RANK[at_or_below_grade]
    results: list[dict[str, Any]] = []
    for row in trends.get("datasets", []):
        entry = manifest_by_id.get(row.get("dataset_id"))
        grade = row.get("reliability_grade")
        if (
            entry is None
            or grade not in RELIABILITY_GRADE_RANK
            or RELIABILITY_GRADE_RANK[grade] < threshold_rank
        ):
            continue
        results.append(
            {
                "id": entry["id"],
                "title": entry["name"],
                "reliability_grade": grade,
                "publish_on_time_pct": row.get("publish_on_time_pct"),
                "reliability_sample_days": row.get("reliability_sample_days"),
                "latest_status": row.get("latest_status"),
                "trend": row.get("trend"),
                "reason": row.get("reason"),
            }
        )
    results.sort(
        key=lambda item: (
            -RELIABILITY_GRADE_RANK[item["reliability_grade"]],
            item["publish_on_time_pct"]
            if isinstance(item["publish_on_time_pct"], (int, float))
            else 101,
            item["id"],
        )
    )
    return results


async def find_unreliable(
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=200,
            description=(
                "Maximum ranked unreliable datasets to return; integer from 1 to "
                "200, e.g. 50."
            ),
            examples=[10, 50],
        ),
    ] = 50,
    at_or_below_grade: Annotated[
        str,
        Field(
            description=(
                "Inclusive reliability threshold; e.g. 'C' returns grades C, D, "
                "and F."
            ),
            examples=["C", "F"],
        ),
    ] = "C",
) -> list[dict[str, Any]]:
    """Expose pipeline-computed publish-reliability decisions."""
    at_or_below_grade = at_or_below_grade.strip().upper()
    valid_thresholds = {"B", "C", "D", "F"}
    if at_or_below_grade not in valid_thresholds:
        raise ValueError(
            "Unknown unreliable grade threshold: "
            f"{at_or_below_grade}. Expected one of: B, C, D, F"
        )
    manifest, trends = await gather(_load_manifest(), _load_trends())
    return _unreliable_results(
        manifest,
        trends,
        at_or_below_grade=at_or_below_grade,
    )[:limit]


_find_unreliable_tool = FunctionTool.from_function(
    find_unreliable,
    title="Identify Unreliable Dataset Publishing",
    description=FIND_UNRELIABLE_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
_find_unreliable_tool.parameters.setdefault("required", [])
mcp.add_tool(_find_unreliable_tool)


def _drift_results(manifest: dict[str, Any], drift: dict[str, Any], *, min_change_count: int) -> list[dict[str, Any]]:
    manifest_by_id = {entry["id"]: entry for entry in manifest.get("datasets", [])}
    results: list[dict[str, Any]] = []
    for row in drift.get("datasets", []):
        entry = manifest_by_id.get(row.get("dataset_id"))
        if entry is None or row.get("verdict") not in {"drift_detected", "record_count_drift"}:
            continue
        shape_changes = row.get("shape_change_count") if isinstance(row.get("shape_change_count"), int) else 0
        column_changes = row.get("column_change_count") if isinstance(row.get("column_change_count"), int) else 0
        if max(shape_changes, column_changes) < min_change_count:
            continue
        results.append({
            "id": entry["id"], "title": entry["name"], "verdict": row["verdict"],
            "shape_changed_recently": row.get("shape_changed_recently"), "shape_change_count": shape_changes,
            "last_shape_change_at": row.get("last_shape_change_at"), "column_count_changed": row.get("column_count_changed"),
            "column_change_count": column_changes, "record_trend": row.get("record_trend"), "record_change_pct": row.get("record_change_pct"),
            "record_count": row.get("record_count"), "column_count": row.get("column_count"), "expected_record_count": row.get("expected_record_count"),
            "record_count_within_tolerance": row.get("record_count_within_tolerance"), "reason": row.get("reason"),
        })
    results.sort(key=lambda item: (0 if item["verdict"] == "drift_detected" else 1, -max(item["shape_change_count"], item["column_change_count"]), item["id"]))
    return results


async def find_schema_drift(
    limit: Annotated[int, Field(ge=1, le=200, description="Maximum ranked drift results to return; integer from 1 to 200, e.g. 50.", examples=[10, 50])] = 50,
    min_change_count: Annotated[int, Field(ge=0, le=100, description="Minimum structural fingerprint or column-count transitions; integer from 0 to 100, e.g. 1.", examples=[0, 1])] = 0,
) -> list[dict[str, Any]]:
    """Expose pipeline-computed schema and record-count drift decisions."""
    manifest, drift = await gather(_load_manifest(), _load_drift())
    return _drift_results(manifest, drift, min_change_count=min_change_count)[:limit]


_find_schema_drift_tool = FunctionTool.from_function(
    find_schema_drift,
    title="Identify Schema and Content Drift",
    description=FIND_SCHEMA_DRIFT_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
_find_schema_drift_tool.parameters.setdefault("required", [])
mcp.add_tool(_find_schema_drift_tool)


def _resolve_reconciliation_dataset(manifest: dict[str, Any], dataset_name: str) -> dict[str, Any]:
    query = dataset_name.strip()
    datasets = [row for row in manifest.get("datasets", []) if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("name"), str)]
    matches = [row for row in datasets if row["id"] == query]
    if not matches:
        matches = [row for row in datasets if row["name"].casefold() == query.casefold()]
    if not matches:
        matches = [row for row in datasets if query.casefold() in row["name"].casefold()]
    if not matches:
        raise ValueError(f"Unknown dataset name or id: {dataset_name}")
    if len(matches) > 1:
        ids = ", ".join(sorted(row["id"] for row in matches))
        raise ValueError(f"Ambiguous dataset name {dataset_name!r}; matching ids: {ids}")
    return matches[0]


def _reconciliation_result(manifest: dict[str, Any], reconciliation: dict[str, Any], dataset_name: str) -> dict[str, Any]:
    entry = _resolve_reconciliation_dataset(manifest, dataset_name)
    group = next((row for row in reconciliation.get("groups", []) if any(member.get("id") == entry["id"] for member in row.get("members", []))), None)
    if group is None:
        return {"matched_dataset_id": entry["id"], "dataset_name": entry["name"], "verdict": "single_source", "group": None, "reason": "No reviewed or conservatively inferred reconciliation group contains this dataset."}
    return {"matched_dataset_id": entry["id"], "group": group}


async def check_reconciliation(
    dataset_name: Annotated[
        str,
        Field(min_length=1, description="Dataset id or name to reconcile, e.g. 'interestrates' or 'Monthly Interest Rates'.", examples=["interestrates", "Monthly Interest Rates"]),
    ],
) -> dict[str, Any]:
    """Return published reconciliation evidence for one resolved dataset."""
    manifest, reconciliation = await gather(_load_manifest(), _load_reconciliation())
    return _reconciliation_result(manifest, reconciliation, dataset_name)


_check_reconciliation_tool = FunctionTool.from_function(
    check_reconciliation,
    title="Check Cross-Source Reconciliation",
    description=CHECK_RECONCILIATION_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
_check_reconciliation_tool.parameters.setdefault("required", [])
mcp.add_tool(_check_reconciliation_tool)


@mcp.tool(
    title="Build Citation-Ready Provenance",
    description=GET_PROVENANCE_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
async def get_provenance(
    dataset_ids: Annotated[
        list[str],
        Field(
            min_length=1,
            max_length=50,
            description=(
                "JSON array of 1 to 50 canonical dataset IDs, e.g. "
                "['fuelprice', 'pricecatcher']."
            ),
            examples=[["fuelprice", "pricecatcher"]],
        ),
    ],
) -> list[dict[str, Any]]:
    """Build provenance and compact published receipts without inference."""
    manifest, health = await _load_catalogue()
    manifest_by_id = {item["id"]: item for item in manifest.get("datasets", [])}
    health_records = _health_by_id(health)
    unknown_ids = [dataset_id for dataset_id in dataset_ids if dataset_id not in manifest_by_id]
    if unknown_ids:
        raise ValueError(f"Unknown dataset id(s): {', '.join(unknown_ids)}")

    provenance = []
    for dataset_id in dataset_ids:
        entry = manifest_by_id[dataset_id]
        health_record = health_records.get(dataset_id, {})
        provenance.append(
            {
                "id": dataset_id,
                "steward": entry.get("steward"),
                "source": entry.get("source"),
                "licence": entry.get("licence"),
                "licence_url": LICENCE_URLS.get(entry.get("licence")),
                "url": entry.get("url"),
                "access_method": health_record.get("access_method", "unknown"),
                "last_verified": health_record.get("last_checked"),
                "schema_version": health.get("schema"),
                "evidence": {
                    **_project_evidence(health_record, COMPACT_EVIDENCE_FIELDS),
                    "available": bool(health_record),
                    "snapshot_checked_at": health.get("checked_at"),
                },
            }
        )
    return provenance


async def get_evidence(
    dataset_id: Annotated[
        str,
        Field(
            min_length=1,
            description="Canonical dataset identifier for a deep receipt, e.g. 'fuelprice'.",
            examples=["fuelprice"],
        ),
    ],
) -> dict[str, Any]:
    """Return all selected evidence fields exactly as published by the pipeline."""
    manifest, health = await _load_catalogue()
    manifest_by_id = {item["id"]: item for item in manifest.get("datasets", [])}
    if dataset_id not in manifest_by_id:
        raise ValueError(f"Unknown dataset id: {dataset_id}")
    health_record = _health_by_id(health).get(dataset_id, {})
    return {
        "dataset_id": dataset_id,
        "schema_version": health.get("schema"),
        "snapshot_checked_at": health.get("checked_at"),
        "evidence_available": bool(health_record),
        "evidence": _project_evidence(health_record, EVIDENCE_FIELDS),
    }


_get_evidence_tool = FunctionTool.from_function(
    get_evidence,
    title="Inspect Published Evidence Receipts",
    description=GET_EVIDENCE_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
_get_evidence_tool.parameters.setdefault("required", [])
mcp.add_tool(_get_evidence_tool)


async def verify_evidence(
    dataset_id: Annotated[
        str,
        Field(
            min_length=1,
            description="Canonical direct-access dataset identifier to re-fetch, e.g. 'fuelprice'.",
            examples=["fuelprice"],
        ),
    ],
) -> dict[str, Any]:
    """Compare safe live transport receipts without mutating published evidence."""
    manifest, health = await _load_catalogue()
    entry = {item["id"]: item for item in manifest.get("datasets", [])}.get(dataset_id)
    if entry is None:
        raise ValueError(f"Unknown dataset id: {dataset_id}")
    health_record = _health_by_id(health).get(dataset_id, {})
    source_url = entry.get("url")
    result = _verification_result_base(dataset_id, source_url, health_record)
    if _is_browser_dependent(entry, health_record):
        result["details"].append(
            "browser-dependent dataset; live verification requires the Camofox sidecar"
        )
        return result
    if not isinstance(source_url, str) or not source_url:
        result["details"].append("dataset has no source URL")
        return result

    key = (dataset_id, source_url, health_record.get("last_checked"))
    async with _VERIFY_LOCK:
        now = monotonic()
        cached = _cached_verification_result(key, now)
        if cached is not None:
            return cached
        try:
            live = await _fetch_live_receipts(source_url)
        except _LiveVerificationBlocked as exc:
            result["details"].append(str(exc))
            return result
        except httpx.RequestError as exc:
            result["verdict"] = "unreachable"
            result["details"].append(f"live request failed: {exc.__class__.__name__}")
            _VERIFY_CACHE[key] = (now, deepcopy(result))
            return result

        result.update({
            "live_request_url": live["request_url"],
            "live_final_url": live["final_url"],
            "live_http_status": live["http_status"],
            "live_last_modified": live["last_modified"],
            "live_content_length": live["content_length"],
        })
        recorded_request_url = health_record.get("request_url")
        result["request_url_match"] = source_url == recorded_request_url if isinstance(recorded_request_url, str) else None
        recorded_http_status = health_record.get("http_status")
        result["http_status_match"] = live["http_status"] == recorded_http_status if isinstance(recorded_http_status, int) else None
        recorded_last_modified = health_record.get("last_modified")
        if recorded_last_modified is not None or live["last_modified"] is not None:
            result["last_modified_match"] = recorded_last_modified == live["last_modified"]
        recorded_content_length = health_record.get("content_length")
        if isinstance(recorded_content_length, int) and isinstance(live["content_length"], int):
            result["content_length_match"] = recorded_content_length == live["content_length"]

        if not 200 <= live["http_status"] < 300:
            result["verdict"] = "unreachable"
            result["details"].append(f"live source returned HTTP {live['http_status']}")
        else:
            mismatches = [field for field in ("request_url_match", "http_status_match", "last_modified_match", "content_length_match") if result[field] is False]
            result["verdict"] = "mismatch" if mismatches else "match"
            result["details"].append(
                ("transport receipt mismatch: " + ", ".join(mismatches))
                if mismatches else "all comparable transport receipts match recorded evidence"
            )
        result["details"].append(
            "content date, record count, and shape fingerprint require the canonical probe pipeline and were not recomputed"
        )
        _VERIFY_CACHE[key] = (now, deepcopy(result))
        return result


_verify_evidence_tool = FunctionTool.from_function(
    verify_evidence,
    title="Re-verify Source Transport Evidence",
    description=VERIFY_EVIDENCE_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
_verify_evidence_tool.parameters.setdefault("required", [])
mcp.add_tool(_verify_evidence_tool)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _latest_live_verification(dataset_id: str) -> str | None:
    rows = [payload.get("verified_at") for (key, (_, payload)) in _VERIFY_CACHE.items() if key[0] == dataset_id]
    return max((value for value in rows if isinstance(value, str)), default=None)


def _reconciliation_for(dataset_id: str, artifact: dict[str, Any]) -> dict[str, Any] | None:
    return next((group for group in artifact.get("groups", []) if any(member.get("id") == dataset_id for member in group.get("members", []))), None)


async def trust_verdict(
    dataset_id: Annotated[str, Field(min_length=1, description="Canonical dataset identifier to aggregate, e.g. 'fuelprice'.", examples=["fuelprice"])]
) -> dict[str, Any]:
    catalogue, trends, drift, reconciliation, attestation_bundle = await gather(
        _load_catalogue(), _load_trends(), _load_drift(), _load_reconciliation(), _load_attestations()
    )
    manifest, health = catalogue
    index, _, scores = attestation_bundle
    entry = next((row for row in manifest.get("datasets", []) if row.get("id") == dataset_id), None)
    if entry is None:
        raise ValueError(f"Unknown dataset id: {dataset_id}")
    ref = index["attestations"].get(dataset_id)
    if not isinstance(ref, str):
        raise RuntimeError(f"No published attestation for dataset id: {dataset_id}")
    envelope = await _fetch_json(ref)
    health_row = _health_by_id(health).get(dataset_id, {})
    trend = next((r for r in trends["datasets"] if r.get("dataset_id") == dataset_id), None)
    drift_row = next((r for r in drift["datasets"] if r.get("dataset_id") == dataset_id), None)
    score = next((r for r in scores["datasets"] if r.get("dataset_id") == dataset_id), None)
    return {
        "dataset_id": dataset_id,
        "facts": envelope["payload"],
        "evidence": {"health": _project_evidence(health_row, EVIDENCE_FIELDS), "trend": trend, "drift": drift_row, "reconciliation": _reconciliation_for(dataset_id, reconciliation)},
        "score": score,
        "signature_ref": ref,
        "citation_text": f"{entry['name']} — {entry['source']}; observed {envelope['payload']['observed_at']}; DataPulse MY attestation {ref}.",
        "observed_at": envelope["payload"]["observed_at"],
        "verified_live_at": _latest_live_verification(dataset_id),
        "validity_notice": "Score reflects data as of observed_at; call verify_evidence for production use.",
    }


_trust_verdict_tool = FunctionTool.from_function(trust_verdict, title="Aggregate a Signed Trust Verdict", description=TRUST_VERDICT_DESCRIPTION, icons=TOOL_ICONS, annotations=READ_ONLY_TOOL_ANNOTATIONS, meta=TOOL_META)
_trust_verdict_tool.parameters.setdefault("required", [])
mcp.add_tool(_trust_verdict_tool)


def _safe_attestation_ref(reference: str, index: dict[str, Any]) -> str:
    ref = index["attestations"].get(reference, reference)
    if not isinstance(ref, str) or not re.fullmatch(r"attestations/[0-9]{4}-[0-9]{2}-[0-9]{2}/[A-Za-z0-9_-]+\.json", ref):
        raise ValueError("Unknown dataset id or unsafe attestation reference")
    return ref


def _iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _daily_head_valid(head: dict[str, Any], registry: dict[str, Any]) -> bool:
    payload = head.get("payload", {}); previous = payload.get("previous_chain_head", "")
    key = next((r for r in registry.get("keys", []) if r.get("key_id") == payload.get("key_id")), None)
    if not key or not re.fullmatch(r"[0-9a-f]{64}", previous): return False
    if hashlib.sha256(_canonical_json(head.get("dataset_links", []))).hexdigest() != payload.get("dataset_links_sha256"): return False
    if hashlib.sha256(bytes.fromhex(previous) + _canonical_json(payload)).hexdigest() != head.get("chain_head"): return False
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key_base64"])).verify(base64.b64decode(head["signature_base64"]), _canonical_json(payload))
    except (InvalidSignature, ValueError, TypeError, KeyError): return False
    return True


async def _verify_git_anchor(anchor: dict[str, Any], expected_head: str) -> bool:
    tag, declared_commit = anchor.get("tag"), anchor.get("commit")
    if not isinstance(tag, str) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag): return False
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.get(f"https://api.github.com/repos/r3dz4r/datapulse-my/git/ref/tags/{tag}"); response.raise_for_status(); target = response.json()["object"]
        if target["type"] == "tag":
            response = await client.get(f"https://api.github.com/repos/r3dz4r/datapulse-my/git/tags/{target['sha']}"); response.raise_for_status(); target = response.json()["object"]
        if target["type"] != "commit" or target["sha"] != declared_commit: return False
        response = await client.get(f"https://raw.githubusercontent.com/r3dz4r/datapulse-my/{target['sha']}/.attestations/chain_head.json"); response.raise_for_status(); committed = response.json()
    return committed.get("chain_head") == expected_head


async def verify_attestation(
    reference: Annotated[str, Field(min_length=1, description="Dataset id or relative digest reference, e.g. 'fuelprice'.", examples=["fuelprice", "attestations/2026-08-15/fuelprice.json"])],
    replay_chain: Annotated[bool, Field(description="Replay daily heads to the newest tag anchor, e.g. true for an auditor.", examples=[False, True])] = False,
) -> dict[str, Any]:
    index, latest_head, _ = await _load_attestations()
    ref = _safe_attestation_ref(reference, index)
    envelope, registry = await gather(_fetch_json(ref), _fetch_json(".well-known/datapulse-probe-keys.json"))
    payload = envelope.get("payload", {}); key = next((r for r in registry.get("keys", []) if r.get("key_id") == payload.get("key_id")), None)
    key_match = bool(key and key.get("public_key_base64") == payload.get("signer_pubkey_base64")); signature_valid = False
    if key_match:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key_base64"])).verify(base64.b64decode(envelope["signature_base64"]), _canonical_json(payload)); signature_valid = True
        except (InvalidSignature, ValueError, TypeError): pass
    previous = payload.get("previous_chain_head", "")
    expected_link = hashlib.sha256(bytes.fromhex(previous) + _canonical_json(payload)).hexdigest() if re.fullmatch(r"[0-9a-f]{64}", previous) else None
    link_valid = expected_link == envelope.get("chain_link")
    observed = _iso_datetime(payload["observed_at"]) if isinstance(payload.get("observed_at"), str) else None
    key_time_valid = bool(key and observed and _iso_datetime(key["not_before"]) <= observed <= _iso_datetime(key["not_after"]))
    l1 = bool(signature_valid and key_match and link_valid and key_time_valid and key.get("algorithm", "Ed25519") == "Ed25519" and key.get("status") != "compromised" and not key.get("compromised_at")) if key else False
    l2 = {"covered": replay_chain, "satisfied": False, "anchor_tag": None, "anchor_commit": None, "reason": "set replay_chain=true"}
    if replay_chain:
        chain_index = await _fetch_json("attestations/chain-index.json"); current = await _fetch_json(f"attestations/{payload['date']}/chain_head.json"); seen = set(); member = any(row.get("dataset_id") == payload.get("dataset_id") and row.get("chain_link") == envelope.get("chain_link") for row in current.get("dataset_links", []))
        while current["chain_head"] not in seen:
            if not member or not _daily_head_valid(current, registry): l2["reason"] = "daily head, membership, or signature is invalid"; break
            seen.add(current["chain_head"]); anchor = chain_index.get("anchors", {}).get(current["chain_head"])
            if anchor and await _verify_git_anchor(anchor, current["chain_head"]): l2 = {"covered": True, "satisfied": True, "anchor_tag": anchor["tag"], "anchor_commit": anchor["commit"], "reason": "signed daily heads replay to a Git-verified tag anchor"}; break
            previous = current["payload"]["previous_chain_head"]
            if previous == ZERO: l2["reason"] = "chain reached genesis without tag anchor"; break
            prior_ref = chain_index.get("heads", {}).get(previous)
            if not prior_ref: l2["reason"] = "previous daily head is not discoverable"; break
            prior = await _fetch_json(prior_ref)
            if prior.get("chain_head") != previous: l2["reason"] = "chain index points to the wrong prior head"; break
            current = prior; member = True
    return {"reference": reference, "digest_ref": ref, "dataset_id": payload.get("dataset_id"), "digest": envelope, "linked_chain_head": payload.get("previous_chain_head"), "latest_chain_head": latest_head.get("chain_head"), "levels": {"L1": {"covered": True, "satisfied": l1, "signature_valid": signature_valid, "key_registry_match": key_match, "key_time_valid": key_time_valid, "chain_link_valid": link_valid}, "L2": l2, "L3": {"covered": False, "satisfied": False, "reason": "call verify_evidence(dataset_id)"}}}


_verify_attestation_tool = FunctionTool.from_function(verify_attestation, title="Verify a Signed Probe Attestation", description=VERIFY_ATTESTATION_DESCRIPTION, icons=TOOL_ICONS, annotations=READ_ONLY_TOOL_ANNOTATIONS, meta=TOOL_META)
_verify_attestation_tool.parameters.setdefault("required", [])
mcp.add_tool(_verify_attestation_tool)


@mcp.tool(
    title="Scope Reusable Data by Licence",
    description=FIND_BY_LICENCE_DESCRIPTION,
    icons=TOOL_ICONS,
    annotations=READ_ONLY_TOOL_ANNOTATIONS,
    meta=TOOL_META,
)
async def find_by_licence(
    licence: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "Exact licence name or supported alias, e.g. "
                "'Creative Commons Attribution 4.0'."
            ),
            examples=[
                "Creative Commons Attribution 4.0",
                "CC BY 4.0",
                "OGL",
            ],
        ),
    ],
) -> dict[str, Any]:
    """Return a canonical licence label, count, and dataset summaries."""
    manifest, health = await _load_catalogue()
    canonical_licence = _canonical_licence(licence)
    health_records = _health_by_id(health)
    datasets = [
        {
            "id": entry["id"],
            "title": entry["name"],
            "source": entry["source"],
            "status": health_records.get(entry["id"], {}).get("status", "unknown"),
        }
        for entry in manifest.get("datasets", [])
        if entry.get("licence", "").casefold() == canonical_licence.casefold()
    ]
    return {
        "licence": canonical_licence,
        "count": len(datasets),
        "datasets": datasets,
    }


@mcp.resource(
    "datapulse://index",
    description=(
        "Read first; lightweight list of all DataPulse MY dataset ids with current "
        "status, title, source, licence, and namespace."
    ),
    mime_type="application/json",
)
async def dataset_index() -> str:
    """Return the lightweight live catalogue index as JSON."""
    manifest, health = await _load_catalogue()
    health_records = _health_by_id(health)
    index = [
        {
            "id": entry["id"],
            "status": health_records.get(entry["id"], {}).get("status", "unknown"),
            "title": entry["name"],
            "source": entry["source"],
            "licence": entry["licence"],
            "namespace": entry.get("namespace", "other"),
        }
        for entry in manifest.get("datasets", [])
    ]
    return json.dumps(index, ensure_ascii=False)


@mcp.resource(
    "datapulse://anomalies",
    description=(
        "Datasets flagged by the latest published anomaly detection, ranked by "
        "severity with pipeline-computed evidence."
    ),
    mime_type="application/json",
)
async def anomaly_resource() -> str:
    """Return all current anomaly results as a JSON array."""
    catalogue, trends = await gather(_load_catalogue(), _load_trends())
    manifest, health = catalogue
    return json.dumps(
        _anomaly_results(manifest, health, trends),
        ensure_ascii=False,
    )


@mcp.resource(
    "datapulse://trends",
    description=(
        "Published per-dataset freshness trends and publish-reliability evidence, "
        "including methodology and aggregate counts."
    ),
    mime_type="application/json",
)
async def trend_resource() -> str:
    """Return the complete published trend artifact as JSON."""
    return json.dumps(await _load_trends(), ensure_ascii=False)


@mcp.resource(
    "datapulse://reliability",
    description=(
        "Live count of DataPulse MY datasets by evaluated publish-reliability grade; "
        "reliability is timeliness, not uptime."
    ),
    mime_type="application/json",
)
async def reliability_summary() -> str:
    """Return the published reliability-grade count object."""
    trends = await _load_trends()
    return json.dumps(
        trends["summary"]["by_reliability_grade"],
        ensure_ascii=False,
    )


@mcp.resource(
    "datapulse://drift",
    description=(
        "Published per-dataset schema and record-count drift evidence, including "
        "methodology and aggregate verdict counts."
    ),
    mime_type="application/json",
)
async def drift_resource() -> str:
    """Return the complete published drift artifact as JSON."""
    return json.dumps(await _load_drift(), ensure_ascii=False)


@mcp.resource(
    "datapulse://reconciliation",
    description="Published cross-source reconciliation groups with pairwise count, date, status, tolerance, and verdict evidence.",
    mime_type="application/json",
)
async def reconciliation_resource() -> str:
    """Return the complete published reconciliation artifact as JSON."""
    return json.dumps(await _load_reconciliation(), ensure_ascii=False)


@mcp.resource(
    "datapulse://attestations",
    description="Latest signed probe attestation index and daily chain head.",
    mime_type="application/json",
)
async def attestation_resource() -> str:
    index, head, _ = await _load_attestations()
    return json.dumps({"index": index, "chain_head": head}, ensure_ascii=False)


@mcp.resource(
    "datapulse://licences",
    description="Live count of DataPulse MY datasets grouped by licence.",
    mime_type="application/json",
)
async def licence_summary() -> str:
    """Return a licence-to-dataset-count JSON object."""
    manifest = await _load_manifest()
    summary: dict[str, int] = {}
    for entry in manifest.get("datasets", []):
        licence = entry["licence"]
        summary[licence] = summary.get(licence, 0) + 1
    return json.dumps(summary, ensure_ascii=False, sort_keys=True)


@mcp.resource(
    "datapulse://{dataset_id}",
    description="Full published manifest entry for one exact DataPulse MY dataset id.",
    mime_type="application/json",
)
async def dataset_resource(dataset_id: str) -> str:
    """Return one on-demand manifest entry without adding inferred fields."""
    manifest = await _load_manifest()
    entry = next(
        (item for item in manifest.get("datasets", []) if item.get("id") == dataset_id),
        None,
    )
    if entry is None:
        raise ValueError(f"Unknown dataset id: {dataset_id}")
    return json.dumps(entry, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)
