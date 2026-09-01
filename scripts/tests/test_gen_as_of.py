from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts/gen_as_of.py"
FIXTURES = ROOT / "scripts/tests/fixtures/as_of"
DATE = "2026-09-01"
BNM_IDS = [
    "bnm_opr", "bnm_base_rate", "bnm_kl_usd_myr", "bnm_interest_rate",
    "bnm_interest_volume", "bnm_interbank_swap", "bnm_kijang_emas", "bnm_myor",
]
GTFS_IDS = [
    "gtfs_static_ktmb", "gtfs_static_prasarana_rail_kl", "gtfs_static_prasarana_bus_kl",
    "gtfs_static_prasarana_bus_penang", "gtfs_static_prasarana_bus_kuantan", "gtfs_static_prasarana_bus_mrtfeeder",
    "gtfs_static_mybas_kangar", "gtfs_static_mybas_alor_setar", "gtfs_static_mybas_kota_bharu", "gtfs_static_mybas_kuala_terengganu",
    "gtfs_static_mybas_ipoh", "gtfs_static_mybas_seremban_a", "gtfs_static_mybas_seremban_b", "gtfs_static_mybas_melaka",
    "gtfs_static_mybas_johor", "gtfs_static_mybas_kuching", "gtfs_realtime_ktmb", "gtfs_realtime_prasarana_bus_kl",
    "gtfs_realtime_prasarana_bus_penang", "gtfs_realtime_prasarana_bus_mrtfeeder", "gtfs_realtime_mybas_kangar",
    "gtfs_realtime_mybas_alor_setar", "gtfs_realtime_mybas_kota_bharu", "gtfs_realtime_mybas_kuala_terengganu",
    "gtfs_realtime_mybas_ipoh", "gtfs_realtime_mybas_seremban_a", "gtfs_realtime_mybas_seremban_b", "gtfs_realtime_mybas_melaka",
    "gtfs_realtime_mybas_johor", "gtfs_realtime_mybas_kuching",
]


def _make_root(tmp_path: Path, family: str) -> Path:
    root = tmp_path / "repo"
    (root / "health").mkdir(parents=True)
    source = "BNM Open API (apikijangportal.bnm.gov.my)" if family == "bnm_open_api" else "data.gov.my (GTFS API)"
    ids = [json.loads(path.read_text(encoding="utf-8"))["dataset_id"] for path in sorted((FIXTURES / family / DATE).glob("*.json"))]
    assert ids == sorted(BNM_IDS if family == "bnm_open_api" else GTFS_IDS)
    (root / "datapulse.json").write_text(json.dumps({"datasets": [{"id": dataset_id, "source": source} for dataset_id in ids]}), encoding="utf-8")
    (root / "health/latest.json").write_text(json.dumps({"checked_at": "2026-09-01T23:00:00Z"}), encoding="utf-8")
    history = [json.dumps({"dataset_id": ids[0], "observed_at": "2026-09-01T10:00:00Z", "status": "fresh"})]
    (root / "health/history.jsonl").write_text("\n".join(history) + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    return root


def _run(root: Path, family: str, date: str = DATE) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(GENERATOR), "--root", str(root), "--family", family, "--date", date], text=True, capture_output=True)


def _tree_digest(path: Path) -> dict[str, str]:
    return {item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest() for item in sorted(path.rglob("*")) if item.is_file()}


def test_bnm_open_api_emits_eight_datasets(tmp_path: Path) -> None:
    root = _make_root(tmp_path, "bnm_open_api")
    assert _run(root, "bnm_open_api").returncode == 0
    target = root / "health/as_of/bnm_open_api" / DATE
    manifest = json.loads((target / "_manifest.json").read_text())
    assert len(list(target.glob("*.json"))) == 9
    assert manifest["actual_dataset_count"] == manifest["expected_dataset_count"] == 8
    assert manifest["missing_history_dataset_ids"] == sorted(set(BNM_IDS) - {"bnm_base_rate"})


def test_gtfs_api_emits_thirty_datasets(tmp_path: Path) -> None:
    root = _make_root(tmp_path, "gtfs_api")
    assert _run(root, "gtfs_api").returncode == 0
    target = root / "health/as_of/gtfs_api" / DATE
    manifest = json.loads((target / "_manifest.json").read_text())
    assert len(list(target.glob("*.json"))) == 31
    assert manifest["actual_dataset_count"] == manifest["expected_dataset_count"] == 30
    assert manifest["missing_history_dataset_ids"] == sorted(set(GTFS_IDS) - {"gtfs_realtime_ktmb"})


def test_missing_history_emits_honest_object(tmp_path: Path) -> None:
    root = _make_root(tmp_path, "bnm_open_api")
    assert _run(root, "bnm_open_api").returncode == 0
    missing = json.loads((root / "health/as_of/bnm_open_api" / DATE / "bnm_interest_rate.json").read_text())
    assert missing == {"_as_of_date": DATE, "dataset_id": "bnm_interest_rate", "family": "bnm_open_api", "observed_at": None, "reason": "no_observation_on_or_before_date", "source_published_at": None}


def test_deterministic_byte_identical_runs(tmp_path: Path) -> None:
    root = _make_root(tmp_path, "bnm_open_api")
    assert _run(root, "bnm_open_api").returncode == 0
    target = root / "health/as_of/bnm_open_api" / DATE
    first = _tree_digest(target)
    assert _run(root, "bnm_open_api").returncode == 0
    assert _tree_digest(target) == first


def test_output_isolated_per_family(tmp_path: Path) -> None:
    root = _make_root(tmp_path, "bnm_open_api")
    assert _run(root, "bnm_open_api").returncode == 0
    assert not (root / "health/as_of/gtfs_api" / DATE).exists()


def test_as_of_date_in_manifest_matches_input(tmp_path: Path) -> None:
    root = _make_root(tmp_path, "bnm_open_api")
    assert _run(root, "bnm_open_api").returncode == 0
    target = root / "health/as_of/bnm_open_api" / DATE
    assert json.loads((target / "_manifest.json").read_text())["as_of_date"] == DATE
    for path in target.glob("*.json"):
        if path.name != "_manifest.json":
            assert json.loads(path.read_text())["_as_of_date"] == DATE


def test_cli_future_date_rejected(tmp_path: Path) -> None:
    root = _make_root(tmp_path, "bnm_open_api")
    result = _run(root, "bnm_open_api", "2026-09-02")
    assert result.returncode != 0
    assert "future" in result.stderr.lower()
