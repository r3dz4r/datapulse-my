"""Pure scheduling and classification policy for DataPulse MY health probes."""

from __future__ import annotations

from datetime import datetime, timezone


REALTIME_FREQUENCIES = {"30 seconds", "hourly"}
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
        or normalized.startswith("daily (weekdays,")
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
    if normalized == "daily" or normalized.startswith("daily (weekdays,"):
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
        if normalized.startswith("daily (weekdays,"):
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
