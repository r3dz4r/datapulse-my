#!/usr/bin/env python3
"""Keep the strict datacontract aligned with explicitly unprobed health rows."""
from __future__ import annotations

import ast
import json
import os
import subprocess
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_datacontract_validation.sh"


def test_health_schema_requires_last_checked_but_permits_null() -> None:
    schema = json.loads((ROOT / "health.schema.json").read_text(encoding="utf-8"))
    row = schema["properties"]["datasets"]["items"]

    assert "last_checked" in row["required"]
    assert set(row["properties"]["last_checked"]["type"]) == {"string", "null"}


def test_runner_predicate_requires_explicit_null_and_unknown_freshness() -> None:
    script = RUNNER.read_text(encoding="utf-8")
    assert "<<'PY'\n" in script, "Runner must define the named unprobed predicate"
    source = script.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    predicates = [
        node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "is_explicitly_unprobed"
    ]
    assert len(predicates) == 1, "Define is_explicitly_unprobed exactly once"
    predicate = predicates[0]
    expression = predicate.body[-1]
    assert isinstance(expression, ast.Return)
    assert isinstance(expression.value, ast.BoolOp)
    assert isinstance(expression.value.op, ast.And), "Both unprobed conditions are required"
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[predicate], type_ignores=[]), str(RUNNER), "exec"), namespace)
    is_unprobed = namespace["is_explicitly_unprobed"]

    assert is_unprobed({"last_checked": None, "status": "unknown-freshness"}) is True
    assert is_unprobed({"status": "unknown-freshness"}) is False
    assert is_unprobed({"last_checked": None}) is False
    schema = json.loads((ROOT / "health.schema.json").read_text(encoding="utf-8"))
    statuses = schema["properties"]["datasets"]["items"]["properties"]["status"]["enum"]
    for status in [*statuses, "invalid-status", None, ""]:
        assert is_unprobed({"last_checked": None, "status": status}) is (status == "unknown-freshness")
        for measured in ["2026-11-08T00:00:00Z", "", False, 0]:
            assert is_unprobed({"last_checked": measured, "status": status}) is False


def test_datacontract_keeps_last_checked_required() -> None:
    contract = yaml.safe_load((ROOT / "datacontract/datapulse.contract.yaml").read_text(encoding="utf-8"))
    health = next(model for model in contract["schema"] if model["name"] == "health_snapshot")
    datasets = next(prop for prop in health["properties"] if prop["name"] == "datasets")
    last_checked = next(prop for prop in datasets["items"]["properties"] if prop["name"] == "last_checked")

    assert last_checked["required"] is True
    assert last_checked["logicalType"] == "string"


def test_runner_logs_exclusions_preserves_other_rows_and_propagates_failure() -> None:
    """Inspect the runner's handoff without requiring datacontract-cli."""
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        stub = work / "datacontract"
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, shutil, sys\n"
            "from pathlib import Path\n"
            "capture = Path(os.environ['CONTRACT_TEST_CAPTURE'])\n"
            "source = Path(sys.argv[2]).parent\n"
            "for name in ('health_snapshot.json', 'datapulse_manifest.json'):\n"
            "    shutil.copyfile(source / name, capture / name)\n"
            "(capture / 'arguments.json').write_text(json.dumps(sys.argv[1:]))\n"
            "sys.exit(int(os.environ['CONTRACT_TEST_STATUS']))\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        health_path = work / "health.json"
        manifest_path = work / "manifest.json"
        manifest_bytes = b'{ "datasets": [{"id": "measured"}] }\n'
        manifest_path.write_bytes(manifest_bytes)
        kept = [
            {"dataset_id": "measured", "last_checked": "2026-11-08T00:00:00Z", "status": "fresh",
             "extra": {"count": 9007199254740993, "value": 1.25, "label": "M\u00e9tadata"}},
            {"dataset_id": "missing-timestamp", "status": "unknown-freshness"},
            {"dataset_id": "null-measured", "last_checked": None, "status": "fresh"},
            {"dataset_id": "null-invalid", "last_checked": None, "status": "invalid-status"},
            {"dataset_id": "timestamp-unknown", "last_checked": "2026-11-08T00:00:00Z", "status": "unknown-freshness"},
        ]
        excluded = [
            {"dataset_id": dataset_id, "last_checked": None, "status": "unknown-freshness"}
            for dataset_id in ("z-unprobed", "a-unprobed")
        ]
        for status, omitted in [(0, excluded), (23, excluded), (0, [])]:
            payload = {"datasets": [omitted[0], kept[0], omitted[1], *kept[1:]] if omitted else kept,
                       "checked_at": "2026-11-08T00:00:00Z", "_trust_summary": {"datasets_total": 7}}
            health_path.write_text(json.dumps(payload), encoding="utf-8")
            original = health_path.read_bytes()
            result = subprocess.run(
                ["bash", str(RUNNER)], cwd=ROOT, capture_output=True, text=True, check=False,
                env={**os.environ, "PATH": str(work) + os.pathsep + os.environ["PATH"],
                     "DATAPULSE_HEALTH_PATH": str(health_path), "DATAPULSE_MANIFEST_PATH": str(manifest_path),
                     "CONTRACT_TEST_CAPTURE": str(work), "CONTRACT_TEST_STATUS": str(status)},
            )

            assert result.returncode == status, result.stdout + result.stderr
            ids = '["a-unprobed", "z-unprobed"]' if omitted else '[]'
            assert f"excluded explicitly unprobed count={len(omitted)} dataset_ids={ids}" in result.stdout
            assert json.loads((work / "health_snapshot.json").read_text()) == {**payload, "datasets": kept}
            assert (work / "datapulse_manifest.json").read_bytes() == manifest_bytes
            assert health_path.read_bytes() == original
            arguments = json.loads((work / "arguments.json").read_text())
            assert arguments[0] == "test"
            assert arguments[2:] == ["--checks", "schema,quality"]
            assert ("contract validation: OK" in result.stdout) is (status == 0)
