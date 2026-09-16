#!/usr/bin/env python3
"""Pilot capture driver for the four-dataset historical-observation cohort.

This module is the thing that makes the pilot accumulate.  Every other module
on this plane (predecessor links, bounded diffs, change reports) operates on
*pairs* of observations; the production store held exactly one observation,
captured by hand, because nothing scheduled ever fetched.  This driver walks
the cohort, fetches each source through the capture entry point, and files
truthful envelopes — but only when a per-dataset cadence gate says the
observation is due.

Why the cadence gate is the core
--------------------------------
The health pipeline runs every 15 minutes.  An ungated per-cycle capture of
``pharmaceutical_products`` (25 MB raw cap, monthly cadence in practice) is
~2.4 GB/day against a 24-month retention policy: the pilot would exhaust its
own storage budget within days while appearing to work.  So before any fetch,
the driver asks the store itself for the dataset's most recent observation
and captures only when the elapsed time meets or exceeds the dataset's
declared refresh interval (weekly 7 days, daily 1 day, hourly 1 hour,
monthly 30 days).  The gate is derived from ``observation_store``'s own
records — never from a separate bookkeeping file, because a second source
of truth for what was captured is how the two drift apart.

When the most-recent-observation lookup itself fails (unreadable index,
unparseable ``observed_at``), the dataset is skipped with that reason and
nothing is captured: capturing against an unreadable index is how
duplicates accumulate.

Isolation and truthfulness
--------------------------
One dataset failing never stops the others: each outcome is recorded
separately with its own reason, and the process exits 0 as long as it ran —
a capture failure is data, not a crash.  A non-zero exit is reserved for a
failure of the driver itself (unreadable manifest, unknown dataset id, a
store root that is or points at the production observation store when
``--allow-production-store`` was not passed).

Only two cohort datasets have a registered normalization profile
(``NORMALIZATION_PROFILES`` below — an explicit constant, no fallback, no
naming-convention inference).  The other two are captured with
``profile=None`` and are reported as ``unprofiled``; a driver that reported
"captured" uniformly would hide that difference.  A projection is only ever
reported as retained when the profile actually produced one.

Profile-designation note: this driver maps ``fuelprice`` to
``fuelprice_csv_v1``, the designation actually registered in
``observation_normalize`` (name ``fuelprice_csv``, version ``v1``).  No
``fuelprice_json`` profile exists anywhere in the registry; passing an
unregistered designation would fail closed inside capture and no projection
could truthfully be claimed.

Source URLs: ``fuelprice`` fetches the manifest's catalogue API
(``api.data.gov.my/data-catalogue?id=fuelprice``) — the 207,030-byte JSON
payload the operator-approved policy basis measured and sized its 2 MiB cap
around.  The storage CSV URL that ``observation_capture``'s fixtures use
(``storage.data.gov.my/opendata/fuelprice/fuelprice.csv``) currently
answers 404 ``NoSuchKey``, so it is not a source this driver can
accumulate from.  Consequence, reported truthfully and never papered over:
the registered ``fuelprice_csv_v1`` profile is a CSV engine, and applying
it to the live JSON payload fails closed inside capture (duplicate-header
guard), so a live fuelprice capture files its bytes and reports
``normalization-failed(profile=fuelprice_csv_v1)`` — no projection exists
and none is claimed.  When a CSV payload arrives (selftest fixtures), the
same profile projects normally.  ``mbpp_weather_stations`` fetches the
FeatureServer ``/query`` form (``f=json&where=1=1&outFields=*
&returnGeometry=false``), because the bare layer URL returns service
metadata with no ``features`` member to project.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Final, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    # Absolute form when the repo root is on sys.path (pipeline, pytest rootdir).
    from scripts.observation_capture import RetrievalResult, capture_observation
    from scripts.observation_store import (
        DEFAULT_ROOT,
        ObservationStoreError,
        list_observations,
        resolve_root,
    )
except ModuleNotFoundError:  # bare form when scripts/ itself is on sys.path
    from observation_capture import RetrievalResult, capture_observation
    from observation_store import (
        DEFAULT_ROOT,
        ObservationStoreError,
        list_observations,
        resolve_root,
    )

__all__ = [
    "CADENCE_INTERVALS",
    "NORMALIZATION_PROFILES",
    "PILOT_COHORT",
    "CadenceError",
    "DatasetOutcome",
    "PilotError",
    "TransportError",
    "main",
    "run_pilot",
]

logger = logging.getLogger(__name__)

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

MANIFEST_PATH: Final[Path] = REPO_ROOT / "datapulse.json"

#: The pilot cohort and the source URL each dataset is fetched from.  The
#: fuelprice URL is the manifest's catalogue API (see module scope); the
#: mbpp URL is the FeatureServer query form that returns feature records
#: rather than layer metadata.
PILOT_COHORT: Final[Mapping[str, str]] = {
    "fuelprice": "https://api.data.gov.my/data-catalogue?id=fuelprice",
    "mbpp_weather_stations": (
        "https://vip.mbpp.gov.my/vipserver/rest/services/Weather_Station/"
        "FeatureServer/50/query?f=json&where=1%3D1&outFields=*&returnGeometry=false"
    ),
    "exchangerates_daily_1700": (
        "https://api.data.gov.my/data-catalogue?id=exchangerates_daily_1700"
    ),
    "pharmaceutical_products": (
        "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv"
    ),
}

#: The only cohort datasets with a registered normalization profile, mapped to
#: their exact registered designations.  Explicit, closed, and fallback-free:
#: a dataset absent from this mapping is captured with ``profile=None`` and
#: must be reported as unprofiled, never defaulted into a success shape.
NORMALIZATION_PROFILES: Final[Mapping[str, str]] = {
    "fuelprice": "fuelprice_csv_v1",
    "mbpp_weather_stations": "mbpp_json_v1",
}

#: Refresh interval by the leading token of the manifest's
#: ``refresh_frequency`` ("daily (weekdays, 1700 MYT)" resolves as daily).
CADENCE_INTERVALS: Final[Mapping[str, timedelta]] = {
    "weekly": timedelta(days=7),
    "daily": timedelta(days=1),
    "hourly": timedelta(hours=1),
    "monthly": timedelta(days=30),
}

USER_AGENT: Final[str] = "Mozilla/5.0 (compatible; DataPulseMY-observation-pilot/1.0)"

DEFAULT_FETCH_TIMEOUT_SECONDS: Final[int] = 60


class PilotError(RuntimeError):
    """The driver itself cannot proceed (bad invocation, unreadable manifest)."""


class CadenceError(PilotError):
    """A dataset's declared refresh cadence cannot be resolved to an interval."""


class TransportError(RuntimeError):
    """A source fetch could not complete; names the URL and the cause."""


@dataclass(frozen=True)
class DatasetOutcome:
    """One dataset's result in one pilot run, reported independently.

    Attributes:
        dataset_id: The cohort dataset this outcome belongs to.
        due: Whether the cadence gate found the dataset due.
        status: ``filed`` (an envelope reached the store), ``skipped``
            (the gate or a precondition declined, nothing fetched or
            filed), or ``failed`` (a fetch or capture error, recorded as
            data rather than crashing the run).
        observation_id: The filed observation id, or None when nothing
            was filed.
        capture_status: The envelope's ``capture_status`` vocabulary
            (``captured | partial | failed | metadata_only |
            not_captured``), or None when nothing was filed.
        projection_state: The driver's truthful projection report; a
            single space-free token (see ``_projection_report``).
        reason: Why this outcome happened; skip reasons name the cadence
            interval or the failing precondition.
        record_count: Retained-projection record count when a profile
            produced one, else None.
    """

    dataset_id: str
    due: bool
    status: str
    observation_id: str | None
    capture_status: str | None
    projection_state: str
    reason: str
    record_count: int | None = None

    @property
    def payload_bytes_retained(self) -> bool:
        """True only when the filing retained payload bytes.

        ``capture_status`` is the envelope's authoritative record and is
        never reinterpreted here; this property is its byte-level
        reading.  Capture's truth rules retain bytes only for
        ``captured`` — every other filed status (``partial``, ``failed``,
        ``metadata_only``, ``not_captured``) files an envelope without
        payload bytes — so the derivation is exactly that invariant.
        """
        return self.capture_status == "captured"

    @property
    def payload(self) -> str:
        """What this outcome's filing actually holds, as a payload token.

        Log-line vocabulary derived from ``capture_status`` alone:
        ``source-bytes`` when payload bytes were retained;
        ``metadata-only(no-payload-bytes)`` when an envelope was filed
        without them; ``none(nothing-filed)`` when nothing was filed at
        all.  Deliberately not a yes/no: a ``captured=no`` next to
        ``status=filed`` reads as a failure verdict over a filing that
        succeeded, which is how an unprofiled dataset's metadata-only
        envelope came to be investigated as a contradiction.  The token
        states what the payload *is*, so the byte-level distinction
        stays visible without implying failure.
        """
        if self.capture_status is None:
            return "none(nothing-filed)"
        if self.capture_status == "captured":
            return "source-bytes"
        return "metadata-only(no-payload-bytes)"

    @property
    def line(self) -> str:
        """One greppable run-log line for this outcome.

        ``status`` is the only success/failure verdict; ``capture_status``
        is the envelope's authoritative record; ``payload`` restates that
        record as what was actually retained, so a filed metadata-only
        observation cannot read as a failed one.
        """
        return (
            f"dataset={self.dataset_id} due={'yes' if self.due else 'no'} "
            f"status={self.status} "
            f"observation_id={self.observation_id or '-'} "
            f"capture_status={self.capture_status or '-'} "
            f"payload={self.payload} "
            f"projection={self.projection_state} reason={self.reason}"
        )


# ---------------------------------------------------------------------------
# Cadence resolution and the gate
# ---------------------------------------------------------------------------


def _describe(interval: timedelta) -> str:
    """Human phrase for an interval, used inside skip reasons."""
    total_seconds = interval.total_seconds()
    if total_seconds >= 86400 and total_seconds % 86400 == 0:
        days = int(total_seconds // 86400)
        return f"{days} day{'s' if days != 1 else ''}"
    if total_seconds >= 3600 and total_seconds % 3600 == 0:
        hours = int(total_seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''}"
    if total_seconds >= 60 and total_seconds % 60 == 0:
        minutes = int(total_seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{total_seconds:.0f}s"


def _interval_for(refresh_frequency: str) -> timedelta:
    """Map a manifest ``refresh_frequency`` string onto its interval.

    The leading token decides: ``daily (weekdays, 1700 MYT)`` is daily.
    Anything unresolvable raises :class:`CadenceError` — a dataset whose
    cadence is unknown is never captured ungated.
    """
    token = refresh_frequency.split("(", 1)[0].split()[0].strip().lower() if refresh_frequency.strip() else ""
    interval = CADENCE_INTERVALS.get(token)
    if interval is None:
        raise CadenceError(
            f"refresh_frequency {refresh_frequency!r} resolves to no known cadence "
            f"(leading token {token!r}); known cadences: {sorted(CADENCE_INTERVALS)}; "
            "a dataset with an unresolvable cadence is never captured ungated"
        )
    return interval


def _parse_instant(value: Any) -> datetime:
    """Parse the index's canonical UTC Z-form instant; ValueError on garbage."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"observed_at {value!r} is not a string")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError(f"observed_at {value!r} carries no timezone offset")
    return moment.astimezone(timezone.utc)


def cadence_gate(
    dataset_id: str,
    interval: timedelta,
    cadence: str,
    *,
    root: Path,
    now: datetime,
) -> tuple[bool, str]:
    """Decide from the store's own records whether ``dataset_id`` is due.

    The most recent observation comes from ``observation_store.
    list_observations`` (newest first), so the gate has no second source of
    truth to drift from.  A failed or unparseable lookup returns not-due
    with the reason: capturing on an unreadable index is how duplicates
    accumulate.
    """
    try:
        rows = list_observations(dataset_id, root=root)
    except (ObservationStoreError, sqlite3.Error, OSError, ValueError) as error:
        return (
            False,
            f"most-recent-observation lookup failed: {type(error).__name__}: {error}; "
            "capturing on an unreadable index is how duplicates accumulate — skipped",
        )
    if not rows:
        return (True, f"no prior observation in store; first capture is always due ({cadence})")
    newest = rows[0]
    try:
        last_observed = _parse_instant(newest.get("observed_at"))
    except ValueError as error:
        return (
            False,
            f"most recent observation {newest.get('observation_id')!r} has an "
            f"unparseable observed_at ({error}); skipped rather than captured blind",
        )
    elapsed = now.astimezone(timezone.utc) - last_observed
    if elapsed >= interval:
        return (
            True,
            f"prior observation {newest['observation_id']} is {_describe(elapsed)} old, "
            f"at or beyond the {_describe(interval)} ({cadence}) refresh interval",
        )
    return (
        False,
        f"cadence-not-due: {_describe(elapsed)} since {newest['observation_id']} "
        f"is inside the {_describe(interval)} ({cadence}) refresh interval",
    )


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def _load_manifest_frequencies() -> dict[str, str]:
    """dataset_id -> refresh_frequency from ``datapulse.json`` (cadence source)."""
    try:
        document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PilotError(f"cannot read manifest {MANIFEST_PATH}: {error}") from error
    entries = document.get("datasets") if isinstance(document, dict) else document
    if not isinstance(entries, list):
        raise PilotError(f"manifest {MANIFEST_PATH} carries no datasets list")
    frequencies: dict[str, str] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            frequency = entry.get("refresh_frequency")
            if isinstance(frequency, str) and frequency:
                frequencies[entry["id"]] = frequency
    return frequencies


# ---------------------------------------------------------------------------
# Transports
# ---------------------------------------------------------------------------


def _now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetch(source_url: str, timeout: int) -> RetrievalResult:
    """One real HTTP GET, recorded truthfully as a RetrievalResult.

    Only complete transfers are returned: ``http.client`` raises on a body
    that ends early, so a truncated read surfaces as :class:`TransportError`
    instead of a ``truncated=True`` filing.  Truncation is never inferred
    from ``Content-Length`` because urllib decodes transfer encodings, which
    would let a compressed hop masquerade as truncation.
    """
    request = Request(source_url, headers={"User-Agent": USER_AGENT}, method="GET")
    started_at = _now_z()
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            status = int(getattr(response, "status", None) or response.getcode())
            headers = response.headers
            final_url = response.geturl()
    except HTTPError as error:
        # A non-200 is a transfer fact, not a crash: capture's decision table
        # files it truthfully (never as a complete capture).
        try:
            body = error.read()
        except Exception:  # noqa: BLE001 — the status is the fact that matters
            body = None
        status = int(error.code)
        headers = error.headers
        final_url = source_url
    except (URLError, TimeoutError, OSError) as error:
        raise TransportError(f"fetch of {source_url} failed: {type(error).__name__}: {error}") from error
    ended_at = _now_z()

    def header(name: str) -> str | None:
        value = headers.get(name) if headers is not None else None
        return value if isinstance(value, str) and value else None

    return RetrievalResult(
        source_url=source_url,
        observed_request_url=final_url,
        http_status=status,
        content_type=header("Content-Type"),
        retrieved_started_at=started_at,
        retrieved_ended_at=ended_at,
        body=body,
        etag=header("ETag"),
        last_modified=header("Last-Modified"),
        source_content_date=None,
        truncated=False,
    )


def _http_transport(timeout: int) -> Callable[[str, str], RetrievalResult]:
    """Live transport: perform the real fetch for each due dataset."""

    def transport(dataset_id: str, source_url: str) -> RetrievalResult:
        logger.info("fetching %s from %s", dataset_id, source_url)
        return _fetch(source_url, timeout)

    return transport


# ---------------------------------------------------------------------------
# Projection truthfulness
# ---------------------------------------------------------------------------


def _projection_report(dataset_id: str, envelope: Mapping[str, Any]) -> tuple[str, int | None]:
    """The driver's projection report token and record count for one filing.

    Never claims a projection the profile did not produce: ``retained`` only
    when the envelope's own ``normalized_projection.state`` is ``retained``;
    an unprofiled dataset says so plainly; a profile whose normalization
    failed (the envelope files state ``unknown``) is reported as failed, not
    as retained and not as unprofiled.
    """
    profile = NORMALIZATION_PROFILES.get(dataset_id)
    projection = envelope.get("normalized_projection")
    projection = projection if isinstance(projection, Mapping) else {}
    if profile is None:
        return ("unprofiled(no-registered-normalization-profile)", None)
    state = projection.get("state")
    if state == "retained":
        count = projection.get("record_count")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            return (f"retained(profile={profile},records={count})", count)
        return (f"retained(profile={profile},records=unknown)", None)
    if state == "unknown":
        return (f"normalization-failed(profile={profile})", None)
    return (f"not-retained(profile={profile},state={state!r})", None)


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------


def run_pilot(
    dataset_ids: Sequence[str],
    *,
    root: Path,
    transport: Callable[[str, str], RetrievalResult],
    now: datetime | None = None,
) -> list[DatasetOutcome]:
    """Drive one pilot pass over ``dataset_ids`` into the store at ``root``.

    Per dataset: resolve the cadence interval from the manifest, consult the
    store-derived gate, fetch only when due, and file through
    ``observation_capture.capture_observation`` (the only writer).  Any
    per-dataset failure becomes that dataset's outcome — it never stops the
    others and never raises out of this function.

    Args:
        dataset_ids: Cohort dataset ids, in run order.
        root: Absolute store root — scratch by default; the production
            root only when the caller's explicit ``--allow-production-store``
            opt-in lifted the CLI refusal (``run_pilot`` itself never
            re-checks: the guard belongs to the invocation boundary where a
            reader can see it in the process arguments).
        transport: Callable ``(dataset_id, source_url) -> RetrievalResult``;
            the selftest injects transports so no network is touched.
        now: Filing/gate instant; defaults to the current UTC time.

    Returns:
        One :class:`DatasetOutcome` per dataset, in argument order.

    Raises:
        PilotError: On driver-level failures only — a dataset id outside
            the cohort, or an unreadable manifest.  Capture and transport
            failures are outcomes, not exceptions.
    """
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    frequencies = _load_manifest_frequencies()
    outcomes: list[DatasetOutcome] = []
    for dataset_id in dataset_ids:
        if dataset_id not in PILOT_COHORT:
            raise PilotError(
                f"dataset {dataset_id!r} is not in the pilot cohort; "
                f"valid ids: {sorted(PILOT_COHORT)}"
            )
        frequency = frequencies.get(dataset_id)
        if frequency is None:
            outcomes.append(
                DatasetOutcome(
                    dataset_id, False, "skipped", None, None, "-",
                    "dataset has no refresh_frequency in datapulse.json; cadence unknown, skipped",
                )
            )
            continue
        try:
            interval = _interval_for(frequency)
        except CadenceError as error:
            outcomes.append(
                DatasetOutcome(dataset_id, False, "skipped", None, None, "-", str(error))
            )
            continue
        due, gate_reason = cadence_gate(
            dataset_id, interval, frequency.split("(", 1)[0].strip(), root=root, now=moment
        )
        if not due:
            outcomes.append(
                DatasetOutcome(dataset_id, False, "skipped", None, None, "-", gate_reason)
            )
            continue
        try:
            retrieval = transport(dataset_id, PILOT_COHORT[dataset_id])
        except Exception as error:  # noqa: BLE001 — isolation is the point
            outcomes.append(
                DatasetOutcome(
                    dataset_id, True, "failed", None, None, "-",
                    f"transport failed: {type(error).__name__}: {error}",
                )
            )
            continue
        try:
            envelope = capture_observation(
                dataset_id,
                retrieval,
                root=root,
                now=moment,
                profile=NORMALIZATION_PROFILES.get(dataset_id),
                store=True,
            )
        except Exception as error:  # noqa: BLE001 — isolation is the point
            outcomes.append(
                DatasetOutcome(
                    dataset_id, True, "failed", None, None, "-",
                    f"capture failed: {type(error).__name__}: {error}",
                )
            )
            continue
        projection_state, record_count = _projection_report(dataset_id, envelope)
        observation_id = envelope.get("observation_id")
        outcomes.append(
            DatasetOutcome(
                dataset_id,
                True,
                "filed",
                observation_id if isinstance(observation_id, str) else None,
                envelope.get("capture_status"),
                projection_state,
                gate_reason,
                record_count,
            )
        )
    return outcomes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_store_root(argument: Path, *, allow_production_store: bool = False) -> Path:
    """Absolute store root; the production root is refused unless opted in.

    ``allow_production_store`` is the CLI's ``--allow-production-store``: an
    explicit, process-visible permission lift, never a default, so a reader
    of the process arguments can tell an intended production capture from a
    mistyped or defaulted ``--store``.  It only lifts the refusal — every
    non-production root behaves exactly as it would without it.
    """
    root = Path(argument).expanduser().resolve()
    if allow_production_store:
        return root
    production_roots = {DEFAULT_ROOT, resolve_root(None)}
    if root in production_roots:
        raise PilotError(
            f"store root {root} is the production observation store root; this pilot "
            "writes only scratch stores — pass a scratch root such as .pilot-scratch"
        )
    return root


def _parse_dataset_selection(selection: str | None) -> list[str]:
    """Parse ``--datasets`` (default: the whole cohort) and validate ids."""
    if selection is None:
        return list(PILOT_COHORT)
    ids = [token.strip() for token in selection.split(",") if token.strip()]
    if not ids:
        raise PilotError("--datasets parsed to an empty selection")
    unknown = [dataset_id for dataset_id in ids if dataset_id not in PILOT_COHORT]
    if unknown:
        raise PilotError(
            f"--datasets names ids outside the pilot cohort: {unknown}; "
            f"valid ids: {sorted(PILOT_COHORT)}"
        )
    return ids


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point.

    Modes:
        ``--selftest``                 Run the five-case acceptance selftest
                                       against injected transports (no
                                       network) and scratch stores inside
                                       the worktree.
        ``--store ROOT``               Live run into a scratch store;
                                       required, and the production store
                                       root is refused unless
                                       ``--allow-production-store`` is
                                       passed.
        ``--allow-production-store``   Explicit opt-in permitting the
                                       production observation store root
                                       for this run — visible in the
                                       process arguments precisely so an
                                       intended production capture is
                                       distinguishable from an accident.
        ``--datasets a,b,...``         Cohort subset (default: all four).
        ``--timeout SECONDS``          Per-fetch HTTP timeout (default 60).
        ``--verbose``                  Debug logging.

    Returns:
        0 when the run executed (per-dataset failures included — they are
        data); 2 only for a failure of the driver itself.
    """
    parser = argparse.ArgumentParser(
        prog="observation_pilot.py",
        description="Pilot capture driver: gated, isolated, truthful observations for the four-dataset cohort.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run the five-case acceptance selftest against injected transports (no network)",
    )
    parser.add_argument(
        "--store",
        type=Path,
        metavar="ROOT",
        help="scratch store root (created if absent); the production observation "
        "store root is refused unless --allow-production-store is passed",
    )
    parser.add_argument(
        "--allow-production-store",
        action="store_true",
        help="explicitly permit the production observation store root for this run; "
        "the default refusal exists so a mistyped --store cannot write the live store",
    )
    parser.add_argument(
        "--datasets",
        metavar="CSV",
        help=f"comma-separated cohort subset (default: all of {','.join(PILOT_COHORT)})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        metavar="SECONDS",
        default=DEFAULT_FETCH_TIMEOUT_SECONDS,
        help=f"per-fetch HTTP timeout in seconds (default {DEFAULT_FETCH_TIMEOUT_SECONDS})",
    )
    parser.add_argument("--verbose", action="store_true", help="debug logging")
    arguments = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if arguments.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if arguments.selftest:
        return _selftest()
    if arguments.store is None:
        print(
            "ERROR --store is required for a live run: this pilot writes scratch "
            "stores by default; the production observation store root additionally "
            "requires --allow-production-store",
            file=sys.stderr,
        )
        return 2
    try:
        root = _resolve_store_root(
            arguments.store, allow_production_store=arguments.allow_production_store
        )
        dataset_ids = _parse_dataset_selection(arguments.datasets)
        outcomes = run_pilot(
            dataset_ids,
            root=root,
            transport=_http_transport(arguments.timeout),
        )
    except PilotError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2

    for outcome in outcomes:
        print(outcome.line)
        logger.debug("outcome %s", outcome)
    filed = sum(1 for outcome in outcomes if outcome.status == "filed")
    with_payload_bytes = sum(1 for outcome in outcomes if outcome.payload_bytes_retained)
    filed_metadata_only = filed - with_payload_bytes
    skipped = sum(1 for outcome in outcomes if outcome.status == "skipped")
    failed = sum(1 for outcome in outcomes if outcome.status == "failed")
    # Counted by payload retention, not "captured": a metadata-only filing is
    # a completed filing, and a summary that says "0 captured" over N filed
    # envelopes has the same reads-as-failure disease as the per-dataset line.
    print(
        f"pilot run complete: {len(outcomes)} dataset(s): {filed} filed "
        f"({with_payload_bytes} with payload bytes, {filed_metadata_only} "
        f"metadata-only), {skipped} skipped by gate, {failed} failed; store={root}"
    )
    return 0


# ---------------------------------------------------------------------------
# Selftest — five cases, injected transports, no network
# ---------------------------------------------------------------------------

_CSV_FUELPRICE: Final[bytes] = (
    "TIMESTAMP,SERIES,RON95,RON97,DIESEL\n"
    "2026-09-10,weekly,2.05,3.35,2.88\n"
    "2026-09-03,weekly,2.05,3.35,2.88\n"
    "2026-08-27,weekly,2.05,3.32,2.85\n"
    "2026-09-10,weekly,2.05,3.35,2.88\n"
).encode("utf-8")

_JSON_MBPP: Final[bytes] = (
    '{"features":['
    '{"attributes":{"station":"STN-01","rain_mm":0.5,"active":1}},'
    '{"attributes":{"station":"STN-02","rain_mm":1.5,"active":1}},'
    '{"attributes":{"station":"STN-01","rain_mm":0.5,"active":1}}'
    "]}"
).encode("utf-8")

_CSV_PHARMACEUTICAL: Final[bytes] = (
    "REGNO,PROD_DESC,STATUS\n"
    "MAL24001,Aspirin 100mg tablet,registered\n"
    "MAL24002,Paracetamol 500mg tablet,registered\n"
).encode("utf-8")


def _fixed_transport(
    body: bytes, content_type: str
) -> Callable[[str, str], RetrievalResult]:
    """Injected transport returning a complete 200 retrieval; no network."""

    def transport(dataset_id: str, source_url: str) -> RetrievalResult:
        stamp = _now_z()
        return RetrievalResult(
            source_url=source_url,
            observed_request_url=source_url,
            http_status=200,
            content_type=content_type,
            retrieved_started_at=stamp,
            retrieved_ended_at=stamp,
            body=body,
            etag=None,
            last_modified=None,
            source_content_date=None,
            truncated=False,
        )

    return transport


def _selftest() -> int:
    """Five acceptance cases against scratch stores; exits 0 only if all pass.

    1. ``cadence-due`` — empty store: the dataset is fetched and filed.
    2. ``cadence-not-due`` — prior observation inside the interval:
       nothing is fetched (the transport raises if called), nothing is
       filed, and the skip reason names the interval.
    3. ``profile-mapped`` — a cohort dataset in the constant captures with
       its projection reported retained and a positive record count.
    4. ``profile-absent`` — a cohort dataset not in the constant captures
       with no projection; the reported state says unprofiled rather than
       defaulting to a success shape.
    5. ``one-dataset-failure-isolated`` — a transport failing for the
       first dataset leaves it reported failed with its reason while the
       second is still captured; the run itself completes.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    failures: list[str] = []

    def verdict(label: str, holds: bool, detail: str) -> None:
        print(f"{'PASS' if holds else 'FAIL'} {label}: {detail}")
        if not holds:
            failures.append(label)

    scratch = Path(tempfile.mkdtemp(prefix=".observation-pilot-selftest-", dir=REPO_ROOT))
    try:
        t0 = datetime.now(timezone.utc)

        # Case 1 — cadence-due: empty store, weekly fuelprice is due.
        first_outcomes = run_pilot(
            ["fuelprice"],
            root=scratch,
            transport=_fixed_transport(_CSV_FUELPRICE, "text/csv"),
            now=t0,
        )
        first = first_outcomes[0]
        print(f"  {first.line}")
        verdict(
            "cadence-due",
            first.due
            and first.status == "filed"
            and first.observation_id is not None
            and first.capture_status == "captured",
            f"fuelprice on an empty store: due={first.due}, filed "
            f"{first.observation_id}, capture_status={first.capture_status}",
        )

        # Case 2 — cadence-not-due: 10 minutes later against a weekly
        # interval.  The transport raises if called, proving the gate
        # short-circuits before any fetch.
        def guard_transport(dataset_id: str, source_url: str) -> RetrievalResult:
            raise AssertionError(
                "transport must not be called when the cadence gate holds"
            )

        second_outcomes = run_pilot(
            ["fuelprice"],
            root=scratch,
            transport=guard_transport,
            now=t0 + timedelta(minutes=10),
        )
        second = second_outcomes[0]
        rows_after = list_observations("fuelprice", root=scratch)
        print(f"  {second.line}")
        verdict(
            "cadence-not-due",
            (not second.due)
            and second.status == "skipped"
            and second.observation_id is None
            and "7 days" in second.reason
            and "weekly" in second.reason
            and len(rows_after) == 1,
            f"10 minutes after the first capture: skipped, store still holds "
            f"{len(rows_after)} observation; reason={second.reason}",
        )

        # Case 3 — profile-mapped: mbpp_weather_stations normalizes under
        # its registered profile and the projection is claimed as retained.
        mbpp_scratch = Path(
            tempfile.mkdtemp(prefix=".observation-pilot-selftest-", dir=REPO_ROOT)
        )
        try:
            third = run_pilot(
                ["mbpp_weather_stations"],
                root=mbpp_scratch,
                transport=_fixed_transport(_JSON_MBPP, "application/json"),
                now=t0,
            )[0]
            print(f"  {third.line}")
            verdict(
                "profile-mapped",
                third.status == "filed"
                and third.capture_status == "captured"
                and third.projection_state.startswith("retained(")
                and "mbpp_json_v1" in third.projection_state
                and third.record_count is not None
                and third.record_count > 0,
                f"mbpp_weather_stations: projection={third.projection_state}",
            )
        finally:
            shutil.rmtree(mbpp_scratch, ignore_errors=True)

        # Case 4 — profile-absent: pharmaceutical_products has no registered
        # profile; bytes are retained but no projection exists or is claimed.
        pharma_scratch = Path(
            tempfile.mkdtemp(prefix=".observation-pilot-selftest-", dir=REPO_ROOT)
        )
        try:
            fourth = run_pilot(
                ["pharmaceutical_products"],
                root=pharma_scratch,
                transport=_fixed_transport(_CSV_PHARMACEUTICAL, "text/csv"),
                now=t0,
            )[0]
            print(f"  {fourth.line}")
            verdict(
                "profile-absent",
                fourth.status == "filed"
                and fourth.capture_status == "captured"
                and fourth.projection_state.startswith("unprofiled(")
                and "no-registered-normalization-profile" in fourth.projection_state
                and fourth.record_count is None,
                f"pharmaceutical_products: bytes captured with "
                f"projection={fourth.projection_state}",
            )
        finally:
            shutil.rmtree(pharma_scratch, ignore_errors=True)

        # Case 5 — one-dataset-failure-isolated: the transport fails for the
        # first dataset and succeeds for the second; both outcomes come
        # back, the failure carries its reason, the capture still lands.
        isolation_scratch = Path(
            tempfile.mkdtemp(prefix=".observation-pilot-selftest-", dir=REPO_ROOT)
        )
        try:
            json_transport = _fixed_transport(_JSON_MBPP, "application/json")

            def selective_transport(dataset_id: str, source_url: str) -> RetrievalResult:
                if dataset_id == "fuelprice":
                    raise TransportError("injected transport failure for fuelprice")
                return json_transport(dataset_id, source_url)

            outcomes = run_pilot(
                ["fuelprice", "mbpp_weather_stations"],
                root=isolation_scratch,
                transport=selective_transport,
                now=t0,
            )
            for outcome in outcomes:
                print(f"  {outcome.line}")
            verdict(
                "one-dataset-failure-isolated",
                len(outcomes) == 2
                and outcomes[0].status == "failed"
                and "injected transport failure" in outcomes[0].reason
                and outcomes[1].status == "filed"
                and outcomes[1].capture_status == "captured",
                f"fuelprice={outcomes[0].status} "
                f"({outcomes[0].reason}), mbpp_weather_stations="
                f"{outcomes[1].status}/{outcomes[1].capture_status}",
            )
        finally:
            shutil.rmtree(isolation_scratch, ignore_errors=True)
    except Exception as error:  # noqa: BLE001 — the selftest reports, never traces
        print(f"FAIL selftest-driver: raised {type(error).__name__}: {error}")
        failures.append("selftest-driver")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        for failure in failures:
            print(f"selftest failed: {failure}", file=sys.stderr)
        return 1
    print("selftest passed: all five cases hold (cadence-due, cadence-not-due, profile-mapped, profile-absent, one-dataset-failure-isolated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
