"""Pure scheduling and classification policy for DataPulse MY health probes."""

from __future__ import annotations

from datetime import datetime, timezone


REALTIME_FREQUENCIES = {"30 seconds", "hourly"}
WEEKDAY_DAILY_FREQUENCIES = {
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
}

SURVEY_FREQUENCY = "biennial to triennial (survey years)"
HEALTH_STATUSES = (
    "fresh",
    "aging",
    "stale",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
)


def _normalized_frequency(frequency: object, manifest_id: str | None = None) -> str:
    if isinstance(frequency, str):
        normalized = frequency.strip().casefold()
    else:
        normalized = ""

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
) -> bool:
    """Return whether a dataset is due, using only the supplied clock value."""
    normalized = _normalized_frequency(frequency, manifest_id)
    checked_at = _as_datetime(last_checked)
    current_time = _as_datetime(now)
    if current_time is None:
        raise ValueError(f"invalid injected now value {now!r}")
    if checked_at is None:
        return True

    tier = frequency_to_tier(normalized, manifest_id)
    return (current_time - checked_at).total_seconds() >= due_interval(tier, normalized)


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


def _survey_status(last_checked: datetime, now: datetime) -> tuple[str, str]:
    verification_age = (now - last_checked).total_seconds() / (24 * 60 * 60)
    if verification_age >= 90:
        return "stale", "survey-verification-stale"
    if verification_age >= 45:
        return "aging", "survey-verification-aging"
    return "fresh", "survey-verification-current"


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

    if _is_browser_dependent(row):
        return "browser-dependent", "browser-access-required"
    if _is_transport_failure(row):
        return "unreachable", "transport-failure"
    if _is_degraded(row):
        return "degraded", "probe-degraded"

    raw_last_checked = row.get("last_checked")
    last_checked = _as_datetime(raw_last_checked)
    if last_checked is None:
        if raw_last_checked is not None:
            return "degraded", "invalid-last-checked"
        unknown_since = _as_datetime(row.get("unknown_since"))
        if unknown_since is not None and (current_time - unknown_since).total_seconds() > 30 * 24 * 60 * 60:
            return "unknown", "unknown-review-required"
        return "unknown", "never-probed"
    if last_checked > current_time:
        return "degraded", "future-last-checked"

    if frequency == SURVEY_FREQUENCY:
        return _survey_status(last_checked, current_time)
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
