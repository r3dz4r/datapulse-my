"""Static contracts for served-surface transport handling."""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/verify_served_release.sh"


def verifier() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_surface_retrieval_requests_compression() -> None:
    source = verifier()
    assert 'curl "${curl_args[@]}" "$url"' in source
    assert "--compressed" in source.split("curl_args=(", 1)[1].split(")", 1)[0]


def test_retrieval_timeout_is_named_and_longer_than_the_old_budget() -> None:
    source = verifier()
    assert 'fetch_max_time="${FETCH_MAX_TIME:-120}"' in source
    assert "--max-time \"$fetch_max_time\"" in source
    assert "--max-time 30" not in source


def test_transport_failure_has_distinct_fail_closed_diagnostic() -> None:
    source = verifier()
    assert "transport failure retrieving" in source
    assert "curl exit code" in source
    assert "elapsed_seconds" in source
    assert "bytes received" in source
    assert 'missing or stale served surface: $surface (HTTP $last_status)' in source
    assert "transport failure retrieving" != "missing or stale served surface"


def test_http_404_is_classified_after_a_non_failing_curl_request() -> None:
    source = verifier()
    curl_block = source.split("metrics=\"$(curl", 1)[1].split("\")", 1)[0]
    assert "--fail" not in curl_block
    assert 'elif [[ "$status" == 404 ]]; then' in source
    assert "--retry-all-errors" in source.split("curl_args=(", 1)[1].split(")", 1)[0]


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        ("--compressed ", "--accept-encoding "),
        ('fetch_max_time="${FETCH_MAX_TIME:-120}"', 'fetch_max_time="30"'),
        ('fail "transport failure retrieving $surface', 'fail "content failure retrieving $surface'),
        ('elif [[ "$status" == 404 ]]; then', 'elif [[ "$status" == 405 ]]; then'),
    ),
)
def test_mutation_controls_reject_each_transport_contract(
    needle: str, replacement: str
) -> None:
    source = verifier()
    mutated = source.replace(needle, replacement, 1)
    assert mutated != source

    if needle == "--compressed ":
        assert "--compressed " not in mutated.split("curl_args=(", 1)[1].split(")", 1)[0]
    elif needle.startswith("fetch_max_time"):
        assert 'fetch_max_time="${FETCH_MAX_TIME:-120}"' not in mutated
    elif needle.startswith('fail "transport failure'):
        assert 'fail "transport failure retrieving $surface' in mutated
    else:
        assert 'elif [[ "$status" == 404 ]]; then' not in mutated
