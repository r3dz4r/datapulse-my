from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import verify_openwiki

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "openwiki-outputs.json"


def test_openwiki_generated_paths_have_one_source() -> None:
    configured = json.loads(CONFIG.read_text(encoding="utf-8"))["generated"]
    printed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "openwiki_output_paths.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    contract = json.loads((ROOT / "scripts" / "contract-scope.json").read_text(encoding="utf-8"))
    contract_openwiki = {
        path
        for path in contract["public_surfaces"]["full_outputs"]
        if path.startswith("openwiki/")
    }

    assert printed == configured
    assert verify_openwiki.GENERATED_PATHS == frozenset(configured)
    # The contract lists four page outputs; the marker is intentionally absent, so assert containment.
    assert contract_openwiki <= set(configured)
