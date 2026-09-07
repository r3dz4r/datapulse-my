"""Tests for reproducible verification latency benchmark summaries."""

from __future__ import annotations

import sys
from pathlib import Path


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))

import verification_benchmark  # noqa: E402


def test_percentiles_use_nearest_rank_and_report_sample_count() -> None:
    assert verification_benchmark._percentiles([1.0, 2.0, 3.0, 4.0]) == {
        "samples": 4,
        "p50_ms": 2.0,
        "p95_ms": 4.0,
        "p99_ms": 4.0,
        "max_ms": 4.0,
    }


def test_percentiles_report_empty_samples_explicitly() -> None:
    assert verification_benchmark._percentiles([]) == {
        "samples": 0,
        "p50_ms": 0.0,
        "p95_ms": 0.0,
        "p99_ms": 0.0,
        "max_ms": 0.0,
    }
