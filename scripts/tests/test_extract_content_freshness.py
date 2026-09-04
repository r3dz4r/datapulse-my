import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/tests/fixtures/kkmnow_blood_01_stock_timeseries.parquet"
POLICY = ROOT / "scripts/probe-policy.json"
SCRIPT = ROOT / "scripts/extract_content_freshness.sh"


def test_content_freshness_helper_returns_the_parquet_canonical_date() -> None:
    """The configured date32 column yields the latest non-future ISO date."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "https://example.invalid/blood.parquet",
            "_parquet_probe_canary_kkmnow_blood",
        ],
        check=True,
        capture_output=True,
        cwd=ROOT,
        env={
            **os.environ,
            "DATAPULSE_CONTENT_FILE": str(FIXTURE),
            "DATAPULSE_PROBE_POLICY": str(POLICY),
        },
        text=True,
    )

    assert result.stdout.strip() == "2022-10-26"
