import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/tests/fixtures/st_energy_balance_2022.pdf"
POLICY = ROOT / "scripts/probe-policy.json"
SCRIPT = ROOT / "scripts/extract_content_freshness.sh"


def test_pdf_year_month_is_extracted_from_st_energy_balance_fixture() -> None:
    """The deterministic ST fixture exercises the shell-to-pdfplumber path."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "https://www.st.gov.my/sites/default/files/2026-02/National_Energy_Balance_2022.pdf",
            "st_energy_balance_pdf",
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

    assert result.stdout.strip() == "2022-01-01"
