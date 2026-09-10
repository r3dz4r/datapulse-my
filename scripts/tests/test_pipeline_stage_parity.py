"""Stage allowlists must stay in lockstep between the emitter and the summarizer.

``check_heartbeat.py`` gates which stages can be *written* (argparse ``choices``).
``summarize_pipeline_telemetry.py`` gates which stages can be *summarized*. They
are maintained as two independent lists, so adding a stage to the emitter alone
breaks the run receipt **silently**: the summarizer raises ``unknown stage``, the
pipeline logs ``pipeline receipt failed; continuing health cycle``, and the unit
still exits 0. Nothing appears to fail while receipts stop being produced.

Regression (2026-09-11): ``passports`` was added to the emitter when passport
generation entered the pipeline, but not to the summarizer. From cycle
``2026-09-10T06:30`` every receipt failed with ``error: line 589: unknown stage``
while ``datapulse-health`` reported success every cycle.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
EMITTER = ROOT / "scripts/check_heartbeat.py"
SUMMARIZER = ROOT / "scripts/summarize_pipeline_telemetry.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _stages(name: str, path: Path) -> frozenset[str]:
    return frozenset(_load(f"datapulse_stage_probe_{name}", path).STAGES)


def test_emitter_and_summarizer_stage_lists_are_identical() -> None:
    emitted = _stages("emitter", EMITTER)
    summarized = _stages("summarizer", SUMMARIZER)

    unsummarizable = sorted(emitted - summarized)
    unwritable = sorted(summarized - emitted)

    assert not unsummarizable, (
        f"stage(s) {unsummarizable} can be written by check_heartbeat.py but are rejected "
        "by summarize_pipeline_telemetry.py, which breaks the run receipt silently. "
        "Add them to its STAGES as well."
    )
    assert not unwritable, (
        f"stage(s) {unwritable} are accepted by summarize_pipeline_telemetry.py but can "
        "never be written by check_heartbeat.py. Either remove them or add them to "
        "check_heartbeat.STAGES."
    )


def test_summarizer_accepts_a_receipt_containing_every_emittable_stage(tmp_path: Path) -> None:
    """Behavioural parity: a full cycle using every emittable stage must summarize."""
    stages = sorted(_stages("emitter", EMITTER))
    telemetry = tmp_path / "stages.jsonl"
    receipt = tmp_path / "receipt.json"

    events = [
        {
            "ts": f"2026-09-11T00:00:{index:02d}Z",
            "stage": stage,
            "duration_ms": 100 + index,
            "status": "success",
            "cycle": "parity-cycle",
            "extra": {},
        }
        for index, stage in enumerate(stages)
    ]
    telemetry.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SUMMARIZER),
            "--input",
            str(telemetry),
            "--output",
            str(receipt),
            "--cycle",
            "parity-cycle",
            "--mode",
            "health-cycle",
            "--source-commit",
            "abcdef1",
            "--health-commit",
            "1234567",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "the summarizer rejected a cycle using stages the emitter can write; "
        f"stderr={result.stderr.strip()}"
    )
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert sorted(payload["stages"]) == stages
    assert payload["failed_stages"] == []


def test_the_passports_regression_is_covered() -> None:
    """The exact stage whose absence broke receipts from 2026-09-10T06:30 onward."""
    assert "passports" in _stages("emitter", EMITTER)
    assert "passports" in _stages("summarizer", SUMMARIZER)
