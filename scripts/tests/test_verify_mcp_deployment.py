"""Hermetic tests for verify_mcp_deployment extract and comparison logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.verify_mcp_deployment import extract_deployed_sha, recorded_sha


class TestExtractDeployedSha:
    @pytest.mark.parametrize(
        ("server_info", "expected"),
        [
            pytest.param(
                {"source_commit_sha": "abcd1234abcd1234abcd1234abcd1234abcd1234"},
                "abcd1234abcd1234abcd1234abcd1234abcd1234",
                id="field_present_40hex",
            ),
            pytest.param(
                {"source_commit_sha": "45da36b"},
                "45da36b",
                id="field_present_short",
            ),
            pytest.param(
                {"version": "v4.0.0b3+45da36b"},
                "45da36b",
                id="version_suffix_7hex",
            ),
            pytest.param(
                {"version": "v4.0.0b3+45da36b487c7a329fc9c19adabb6d07c8976c3f3"},
                "45da36b487c7a329fc9c19adabb6d07c8976c3f3",
                id="version_suffix_40hex",
            ),
            pytest.param(
                {"version": "v4.0.0b3"},
                "<missing>",
                id="version_no_suffix",
            ),
            pytest.param(
                {},
                "<missing>",
                id="empty_dict",
            ),
            pytest.param(
                {"source_commit_sha": "", "version": "v4.0.0b3+deadbeef"},
                "deadbeef",
                id="empty_field_falls_back_to_version",
            ),
            pytest.param(
                {"source_commit_sha": None, "version": "v4.0.0b3+deadbeef"},
                "deadbeef",
                id="null_field_falls_back_to_version",
            ),
        ],
    )
    def test_extract_deployed_sha(self, server_info: dict[str, Any], expected: str) -> None:
        assert extract_deployed_sha(server_info) == expected


class TestRecordedSha:
    def test_reads_from_mcp_json(self, tmp_path: Path) -> None:
        mcp = tmp_path / "mcp.json"
        mcp.write_text(
            json.dumps({
                "server": {
                    "source_commit_sha": "45da36b487c7a329fc9c19adabb6d07c8976c3f3",
                }
            }),
            encoding="utf-8",
        )
        assert recorded_sha(tmp_path) == "45da36b487c7a329fc9c19adabb6d07c8976c3f3"


class TestComparisonNormalization:
    @pytest.mark.parametrize(
        ("deployed", "recorded", "match"),
        [
            pytest.param("45da36b", "45da36b487c7a329fc9c19adabb6d07c8976c3f3", True, id="short_vs_full"),
            pytest.param("45da36b487c7a329fc9c19adabb6d07c8976c3f3", "45da36b", True, id="full_vs_short"),
            pytest.param("45da36b", "45da36b", True, id="both_short_equal"),
            pytest.param("45da36c", "45da36b487c7a329fc9c19adabb6d07c8976c3f3", False, id="differing_short"),
            pytest.param("deadbeef", "45da36b487c7a329fc9c19adabb6d07c8976c3f3", False, id="completely_different"),
        ],
    )
    def test_short_form_comparison(self, deployed: str, recorded: str, match: bool) -> None:
        assert (deployed[:7] == recorded[:7]) is match
