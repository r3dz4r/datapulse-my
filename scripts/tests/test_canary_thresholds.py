"""Focused tests for per-adapter canary record-count thresholds."""

from scripts.run_health_canary import classify_record_count


def test_direct_10pct_threshold() -> None:
    classification, category, _ = classify_record_count(100, 112, "direct")

    assert (classification, category) == ("Blocker", "Structural")


def test_direct_5pct_threshold() -> None:
    classification, category, _ = classify_record_count(100, 105, "direct")

    assert (classification, category) == ("Approved", "Structural")


def test_gtfs_realtime_15pct_volatile() -> None:
    classification, category, _ = classify_record_count(100, 85, "gtfs-realtime")

    assert (classification, category) == ("Volatile", "Volatile")


def test_gtfs_realtime_60pct_blocker() -> None:
    classification, category, _ = classify_record_count(100, 40, "gtfs-realtime")

    assert (classification, category) == ("Blocker", "Operational")


def test_gtfs_realtime_2_to_0_blocker() -> None:
    classification, category, reason = classify_record_count(2, 0, "gtfs-realtime")

    assert (classification, category) == ("Blocker", "Operational")
    assert "upstream stall" in reason
