"""Pure scheduling and classification policy for DataPulse MY health probes."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REALTIME_FREQUENCIES = {"30 seconds", "hourly"}
# Operator-approved 2026-11-08: a 30-second feed gets its own one-minute tier
# instead of sharing the 15-minute realtime tier with hourly feeds.
REALTIME_30S_FREQUENCIES = {"30 seconds"}
WEEKDAY_DAILY_FREQUENCIES = {
    # Declared by two manifest datasets; scripts/check.sh already schedules it
    # with the other weekday cadences (`startswith("daily (weekdays")`).
    "daily (weekdays)",
    "daily (weekdays, 0900 myt)",
    "daily (weekdays, 1130 myt)",
    "daily (weekdays, 1200 myt)",
    "daily (weekdays, 1700 myt)",
}
WEEKLY_MONTHLY_FREQUENCIES = {"weekly", "monthly", "quarterly"}
SLOW_FREQUENCIES = {
    "annual",
    "as-required",
    "biennial to triennial (survey years)",
}

TIER_DUE_SECONDS = {
    "realtime-30s": 60,
    "realtime": 15 * 60,
    "daily": 24 * 60 * 60,
    "weekly-monthly": 7 * 24 * 60 * 60,
    "slow": 30 * 24 * 60 * 60,
}

FRESHNESS_BASELINE_SECONDS = {
    "30 seconds": 30,
    "hourly": 60 * 60,
    "daily": 24 * 60 * 60,
    "weekly": 7 * 24 * 60 * 60,
    "monthly": 30 * 24 * 60 * 60,
    "quarterly": 90 * 24 * 60 * 60,
    "annual": 365 * 24 * 60 * 60,
    # The served classifier in scripts/check.sh reads this cadence as 730 days
    # (`elif $frequency | startswith("biennial") then 730`), so the published
    # rule has to describe the behaviour a reader would actually observe. 730 is
    # the two-year lower bound of the publisher's "biennial to triennial" cycle,
    # not its three-year upper bound: a 1095-day baseline here would promise a
    # looser threshold than the service enforces. This value and the check.sh
    # cadence map must move together.
    "biennial to triennial (survey years)": 730 * 24 * 60 * 60,
}

# The publisher's own cadence vocabulary, as declared on the data.gov.my
# catalogue pages on 2026-09-26, measured per dataset across the 327 the audit
# examined (YEARLY 138, INFREQUENT 11, ONE-OFF 1; total 150) and per page
# across the 290 captured (YEARLY 116, INFREQUENT 11, ONE-OFF 1); the two
# denominators differ, so do not conflate them. Our policy predates that page
# surface and only knows "annual" and "as-required", so a cadence read from a
# catalogue page would otherwise raise in `_normalized_frequency`. These are a
# bounded set of measured synonyms, not a catch-all: a cadence outside our
# vocabulary and outside this map must still raise, so a publisher cannot
# invent a new word into the schedule.
PUBLISHER_FREQUENCY_ALIASES = {
    "yearly": "annual",
    "one-off": "as-required",
    "infrequent": "as-required",
}

SURVEY_FREQUENCY = "biennial to triennial (survey years)"
NO_CLOCK_DATA_TYPES = {"reference", "policy-reference"}
HEALTH_STATUSES = (
    "fresh",
    "aging",
    "stale",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
    "reference",
)


def _normalized_frequency(frequency: object, manifest_id: str | None = None) -> str:
    if isinstance(frequency, str):
        normalized = frequency.strip().casefold()
    else:
        normalized = ""

    normalized = PUBLISHER_FREQUENCY_ALIASES.get(normalized, normalized)

    if (
        normalized in REALTIME_FREQUENCIES
        or normalized in WEEKLY_MONTHLY_FREQUENCIES
        or normalized in SLOW_FREQUENCIES
        or normalized == "daily"
        or normalized in WEEKDAY_DAILY_FREQUENCIES
    ):
        return normalized

    identifier = manifest_id if manifest_id is not None else "<unknown>"
    raise ValueError(
        f"manifest ID {identifier!r} has unsupported refresh_frequency {frequency!r}"
    )


def frequency_to_tier(frequency: object, manifest_id: str | None = None) -> str:
    """Map one manifest refresh frequency to its probe scheduling tier."""
    normalized = _normalized_frequency(frequency, manifest_id)
    if normalized in REALTIME_30S_FREQUENCIES:
        return "realtime-30s"
    if normalized in REALTIME_FREQUENCIES:
        return "realtime"
    if normalized == "daily" or normalized in WEEKDAY_DAILY_FREQUENCIES:
        return "daily"
    if normalized in WEEKLY_MONTHLY_FREQUENCIES:
        return "weekly-monthly"
    return "slow"


def due_interval(tier: str, frequency: object | None = None) -> int:
    """Return a tier's probe interval, including the weekday-daily override."""
    if tier not in TIER_DUE_SECONDS:
        raise ValueError(f"unsupported health scheduling tier {tier!r}")
    if tier == "daily" and frequency is not None:
        normalized = _normalized_frequency(frequency)
        if normalized in WEEKDAY_DAILY_FREQUENCIES:
            return 60 * 60
    return TIER_DUE_SECONDS[tier]


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_due(
    last_checked: object,
    now: datetime,
    frequency: object,
    manifest_id: str | None = None,
    *,
    interval_seconds: float | None = None,
) -> bool:
    """Return whether a dataset is due, using only the supplied clock value.

    ``interval_seconds`` replaces the declared cadence's interval for callers
    that have already resolved a retry or operator override; the frequency is
    still validated so an unknown cadence raises either way.
    """
    normalized = _normalized_frequency(frequency, manifest_id)
    checked_at = _as_datetime(last_checked)
    current_time = _as_datetime(now)
    if current_time is None:
        raise ValueError(f"invalid injected now value {now!r}")
    if checked_at is None:
        return True

    if interval_seconds is None:
        tier = frequency_to_tier(normalized, manifest_id)
        interval_seconds = due_interval(tier, normalized)
    return (current_time - checked_at).total_seconds() >= interval_seconds


DEFAULT_RETRY_SECONDS = 240 * 60
RETRYABLE_BROWSER_MESSAGE = re.compile("unavailable|failed|error", re.IGNORECASE)


def probe_interval(
    previous_row: dict[str, object],
    frequency: object,
    manifest_id: str | None = None,
    *,
    cadence_override_seconds: float | None = None,
    retry_seconds: float = DEFAULT_RETRY_SECONDS,
) -> float:
    """Resolve one dataset's probe interval from its declared cadence and last outcome.

    Mirrors the failure retry rules of `scripts/check.sh --due`: an unreachable
    dataset is retried no later than its own declared refresh (30 seconds for a
    30-second feed), even under a longer retry or cadence override; a degraded
    or failed browser probe retries on the retry cadence.
    """
    normalized = _normalized_frequency(frequency, manifest_id)
    tier = frequency_to_tier(normalized, manifest_id)
    declared = due_interval(tier, normalized)
    cadence = declared if cadence_override_seconds is None else cadence_override_seconds
    status = previous_row.get("status")
    message = previous_row.get("message")
    if status == "unreachable":
        retry_limit = (
            FRESHNESS_BASELINE_SECONDS["30 seconds"]
            if normalized in REALTIME_30S_FREQUENCIES
            else declared
        )
        return min(retry_seconds, cadence, retry_limit)
    if status == "degraded" or (
        status == "browser-dependent"
        and isinstance(message, str)
        and RETRYABLE_BROWSER_MESSAGE.search(message)
    ):
        return retry_seconds
    return cadence


def select_due(
    manifest_rows: list[dict],
    previous_rows: list[dict],
    now: datetime,
    *,
    tier: str | None = None,
    cadence_override_seconds: float | None = None,
    retry_seconds: float = DEFAULT_RETRY_SECONDS,
) -> list[dict]:
    """Return the manifest entries due for a probe at ``now``, in manifest order.

    A dataset is selected exactly when `is_due` says so for its previous
    ``last_checked`` and declared ``refresh_frequency``. Every entry's cadence is
    validated, so an unknown cadence raises rather than being skipped.
    """
    if tier is not None and tier not in TIER_DUE_SECONDS:
        raise ValueError(f"unsupported health scheduling tier {tier!r}")
    previous_by_id: dict[object, dict] = {}
    for row in previous_rows:
        if isinstance(row, dict):
            previous_by_id.setdefault(row.get("dataset_id"), row)

    selected = []
    for entry in manifest_rows:
        dataset_id = entry.get("id")
        identifier = dataset_id if isinstance(dataset_id, str) else None
        frequency = entry.get("refresh_frequency")
        if tier is not None and frequency_to_tier(frequency, identifier) != tier:
            continue
        previous = previous_by_id.get(dataset_id, {})
        interval = probe_interval(
            previous,
            frequency,
            identifier,
            cadence_override_seconds=cadence_override_seconds,
            retry_seconds=retry_seconds,
        )
        if is_due(previous.get("last_checked"), now, frequency, identifier, interval_seconds=interval):
            selected.append(entry)
    return selected


def _valid_signal(value: object, observed_at: datetime | None) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return None, "invalid"
    parsed = _as_datetime(value)
    if parsed is None:
        return None, "invalid"
    if observed_at is not None and parsed > observed_at:
        return None, "future"
    return value.strip(), None


def select_freshness_signal(row: dict[str, object]) -> tuple[str | None, str]:
    """Select validated content freshness, then its configured HTTP fallback."""
    observed_at = _as_datetime(row.get("last_checked"))
    policy = row.get("freshness_policy")
    policy = policy if isinstance(policy, dict) else {}
    mode = policy.get("mode")
    fallback = policy.get("fallback", "last-modified")
    content_value = row.get("content_freshness_date")
    last_modified = row.get("last_modified")

    content_error = None
    if mode != "structural-hash" and content_value is not None:
        content_signal, content_error = _valid_signal(content_value, observed_at)
        if content_signal is not None:
            return content_signal, "content-date"

    should_fallback = mode == "structural-hash" or fallback == "last-modified"
    header_error = None
    if should_fallback and last_modified is not None:
        header_signal, header_error = _valid_signal(last_modified, observed_at)
        if header_signal is not None:
            reason = "last-modified-fallback" if policy or content_value is not None else "last-modified"
            return header_signal, reason

    if content_error == "future":
        return None, "future-content-date"
    if header_error == "future":
        return None, "future-last-modified"
    if content_error == "invalid" or header_error == "invalid":
        return None, "invalid-freshness-signals"
    return None, "no-freshness-signal"


def age_in_days(row: dict[str, object], now: datetime) -> float | None:
    """Calculate non-negative freshness age from the selected validated signal."""
    current_time = _as_datetime(now)
    if current_time is None:
        raise ValueError(f"invalid injected now value {now!r}")
    signal, _ = select_freshness_signal(row)
    signal_time = _as_datetime(signal)
    if signal_time is None or signal_time > current_time:
        return None
    return (current_time - signal_time).total_seconds() / (24 * 60 * 60)


def _is_browser_dependent(row: dict[str, object]) -> bool:
    access_method = row.get("access_method")
    return isinstance(access_method, str) and access_method.strip().casefold() == "camofox"


def _is_transport_failure(row: dict[str, object]) -> bool:
    probe_status = row.get("probe_status")
    if isinstance(probe_status, str) and probe_status.casefold() == "unreachable":
        return True
    http_status = row.get("http_status")
    return isinstance(http_status, int) and not 200 <= http_status < 300


def _is_degraded(row: dict[str, object]) -> bool:
    probe_status = row.get("probe_status")
    return isinstance(probe_status, str) and probe_status.casefold() == "degraded"


def _as_required_status(row: dict[str, object], now: datetime) -> tuple[str, str]:
    policy = row.get("freshness_policy")
    policy = policy if isinstance(policy, dict) else {}
    field = policy.get("content_date_field")
    if not isinstance(field, str) or not field.casefold().startswith("date_"):
        return "unknown-freshness", "as-required-no-publisher-date"

    signal, reason = select_freshness_signal(row)
    signal_time = _as_datetime(signal)
    if reason == "content-date" and signal_time is not None and signal_time <= now:
        return "fresh", "as-required-publisher-date"
    return "unknown-freshness", reason


def classify_status(row: dict[str, object], now: datetime) -> tuple[str, str]:
    """Classify normalized probe evidence using the public status precedence."""
    current_time = _as_datetime(now)
    if current_time is None:
        raise ValueError(f"invalid injected now value {now!r}")

    frequency = _normalized_frequency(row.get("refresh_frequency"), str(row.get("dataset_id", "<unknown>")))

    if _is_transport_failure(row):
        return "unreachable", "transport-failure"
    if row.get("data_type") in NO_CLOCK_DATA_TYPES:
        return "reference", "versioned-reference-data"
    if _is_degraded(row):
        return "degraded", "probe-degraded"

    raw_last_checked = row.get("last_checked")
    last_checked = _as_datetime(raw_last_checked)
    if last_checked is None:
        if raw_last_checked is not None:
            return "degraded", "invalid-last-checked"
        # Browser-rendered rows carry no direct HTTP status, so the transport
        # branch above cannot see them. A browser probe that took no measurement
        # at all is the one case that stays browser-dependent; a measured one is
        # graded on its freshness signal below exactly like any other row.
        if _is_browser_dependent(row):
            return "browser-dependent", "browser-access-required"
        unknown_since = _as_datetime(row.get("unknown_since"))
        if unknown_since is not None and (current_time - unknown_since).total_seconds() > 30 * 24 * 60 * 60:
            return "unknown", "unknown-review-required"
        return "unknown", "never-probed"
    if last_checked > current_time:
        return "degraded", "future-last-checked"

    if frequency == "as-required":
        return _as_required_status(row, current_time)

    signal, signal_reason = select_freshness_signal(row)
    freshness_age = age_in_days(row, current_time)
    if signal is None or freshness_age is None:
        return "unknown-freshness", signal_reason

    baseline_frequency = "daily" if frequency in WEEKDAY_DAILY_FREQUENCIES else frequency
    baseline_seconds = FRESHNESS_BASELINE_SECONDS[baseline_frequency]
    age_seconds = freshness_age * 24 * 60 * 60
    if age_seconds <= baseline_seconds * 1.5:
        return "fresh", "freshness-within-window"
    if age_seconds <= baseline_seconds * 3:
        return "aging", "freshness-aging"
    return "stale", "freshness-stale"


def _rows_by_id(rows: list[dict], source: str) -> dict[str, dict]:
    indexed = {}
    for row in rows:
        dataset_id = row.get("dataset_id")
        if not isinstance(dataset_id, str) or not dataset_id:
            raise ValueError(f"{source} row has invalid dataset_id {dataset_id!r}")
        if dataset_id in indexed:
            raise ValueError(f"duplicate dataset ID {dataset_id!r} in {source}")
        indexed[dataset_id] = row
    return indexed


def merge_due_updates(
    prior_rows: list[dict],
    updates: list[dict],
    manifest_ids: list[str],
) -> list[dict]:
    """Replace selected prior rows and return the exact manifest ID order."""
    if len(set(manifest_ids)) != len(manifest_ids):
        raise ValueError("duplicate dataset ID in manifest_ids")

    prior_by_id = _rows_by_id(prior_rows, "prior_rows")
    updates_by_id = _rows_by_id(updates, "updates")
    manifest_id_set = set(manifest_ids)
    unknown_ids = (set(prior_by_id) | set(updates_by_id)) - manifest_id_set
    if unknown_ids:
        raise ValueError(f"unknown dataset IDs outside manifest: {sorted(unknown_ids)!r}")

    merged_by_id = prior_by_id | updates_by_id
    missing_ids = manifest_id_set - set(merged_by_id)
    if missing_ids:
        raise ValueError(f"missing dataset IDs after due merge: {sorted(missing_ids)!r}")
    return [merged_by_id[dataset_id] for dataset_id in manifest_ids]


def derive_trust_summary(rows: list[dict]) -> dict:
    """Derive health arithmetic and stale evidence solely from final rows."""
    by_status = {
        status.replace("-", "_"): sum(row.get("status") == status for row in rows)
        for status in HEALTH_STATUSES
    }
    signal_sources = {
        "last_modified_header": sum(
            row.get("freshness_signal_source") == "last_modified_header" for row in rows
        ),
        "content_date_parse": sum(
            row.get("freshness_signal_source") == "content_date_parse" for row in rows
        ),
        "neither": sum(row.get("freshness_signal_source") == "none" for row in rows),
    }
    last_modified_values = [
        value
        for row in rows
        if isinstance((value := row.get("last_modified")), str)
    ]
    stale_datasets = sorted(
        (
            {
                "dataset_id": row.get("dataset_id"),
                "days_since_modified": row.get("staleness_days"),
            }
            for row in rows
            if row.get("status") == "stale"
        ),
        key=lambda row: (
            isinstance(row["days_since_modified"], (int, float)),
            row["days_since_modified"] if isinstance(row["days_since_modified"], (int, float)) else -1,
        ),
        reverse=True,
    )
    return {
        "datasets_total": len(rows),
        "by_status": by_status,
        "datasets_health_signal_source": signal_sources,
        "datasets_with_no_last_modified_header": sum(
            row.get("last_modified") is None for row in rows
        ),
        "datasets_with_no_record_count_extracted": sum(
            row.get("record_count") is None for row in rows
        ),
        "oldest_last_modified": min(last_modified_values, default=None),
        "newest_last_modified": max(last_modified_values, default=None),
        "stale_datasets": stale_datasets,
    }


def _read_json_document(path: Path) -> object:
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if text.strip() else {}


def _atomic_write_text(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    """`select-due`: write the manifest restricted to the datasets due at --now-epoch."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    select = commands.add_parser("select-due", help="filter a manifest to the datasets due for a probe")
    select.add_argument("--manifest", type=Path, required=True)
    select.add_argument("--previous", type=Path, required=True, help="prior health snapshot; may be empty")
    select.add_argument("--now-epoch", type=int, required=True, help="injected clock, UTC epoch seconds")
    select.add_argument("--tier", choices=sorted(TIER_DUE_SECONDS))
    select.add_argument("--cadence-minutes", type=int)
    select.add_argument("--retry-minutes", type=int, default=DEFAULT_RETRY_SECONDS // 60)
    select.add_argument("--output", type=Path, help="write atomically here instead of stdout")
    args = parser.parse_args(argv)
    for name in ("cadence_minutes", "retry_minutes"):
        value = getattr(args, name)
        if value is not None and value < 1:
            parser.error(f"--{name.replace('_', '-')} must be a positive integer")

    manifest = _read_json_document(args.manifest)
    previous = _read_json_document(args.previous)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("datasets"), list):
        parser.error(f"invalid dataset manifest: {args.manifest}")
    previous_rows = previous.get("datasets", []) if isinstance(previous, dict) else []
    try:
        due = select_due(
            manifest["datasets"],
            previous_rows if isinstance(previous_rows, list) else [],
            datetime.fromtimestamp(args.now_epoch, tz=timezone.utc),
            tier=args.tier,
            cadence_override_seconds=None if args.cadence_minutes is None else args.cadence_minutes * 60,
            retry_seconds=args.retry_minutes * 60,
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    content = json.dumps({**manifest, "datasets": due}, ensure_ascii=False) + "\n"
    if args.output is None:
        sys.stdout.write(content)
    else:
        _atomic_write_text(args.output, content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
