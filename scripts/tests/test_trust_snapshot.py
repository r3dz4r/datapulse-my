import hashlib
import json
import os
from pathlib import Path
import subprocess


SCRIPT = Path(__file__).parents[1] / "gen_trust_snapshot.py"
FAKE_DATE = "2026-08-09"


def _git(repo: Path, *args: str, date: str | None = None) -> str:
    env = os.environ.copy()
    if date:
        env.update({"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
    return subprocess.run(
        ["git", *args], cwd=repo, env=env, check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def _write_inputs(repo: Path, statuses: dict[str, str], record_count: int) -> None:
    datasets = [
        {
            "dataset_id": dataset_id,
            "name": dataset_id.title(),
            "namespace": "test",
            "licence": "MIT",
            "status": status,
            "last_checked": "2026-08-09T00:00:00Z",
        }
        for dataset_id, status in statuses.items()
    ]
    (repo / "changelog.json").write_text(
        json.dumps({"datasets": datasets}), encoding="utf-8"
    )
    (repo / "datapulse.json").write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "id": row["dataset_id"],
                        "namespace": row["namespace"],
                        "licence": row["licence"],
                    }
                    for row in datasets
                ]
            }
        ),
        encoding="utf-8",
    )
    health = {
        "datasets": [
            {
                "dataset_id": dataset_id,
                "status": status,
                "last_checked": "2026-08-09T00:00:00Z",
                "record_count": record_count if dataset_id == "alpha" else 5,
                "column_count": 2,
                "first_row_hash": "old" if record_count == 10 else "new",
            }
            for dataset_id, status in statuses.items()
        ]
    }
    (repo / "health").mkdir(exist_ok=True)
    (repo / "health/latest.json").write_text(json.dumps(health), encoding="utf-8")


def _make_repo(tmp_path: Path, *, short_history: bool = False) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / "data").mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")

    old_date = "2026-08-08T00:00:00Z" if short_history else "2026-07-31T00:00:00Z"
    _write_inputs(repo, {"alpha": "fresh", "beta": "stale"}, 10)
    for dataset_id in ("alpha", "beta"):
        (repo / "data" / f"{dataset_id}.md").write_text(dataset_id, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "old snapshot", date=old_date)

    if not short_history:
        _write_inputs(
            repo,
            {"alpha": "stale", "beta": "fresh", "gamma": "unknown-freshness"},
            12,
        )
        (repo / "data/gamma.md").write_text("gamma", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "current snapshot", date="2026-08-09T00:00:00Z")
    return repo


def _run(repo: Path) -> tuple[Path, Path]:
    env = os.environ.copy()
    env.update({"FAKE_DATE": FAKE_DATE, "DATAPULSE_REPO_ROOT": str(repo)})
    subprocess.run(["python3", str(SCRIPT)], cwd=repo, env=env, check=True)
    base = repo / "docs" / f"trust-snapshot-{FAKE_DATE}"
    return base.with_suffix(".md"), base.with_suffix(".json")


def test_generates_md_and_json_for_today(tmp_path: Path) -> None:
    markdown_path, json_path = _run(_make_repo(tmp_path))

    assert markdown_path.exists() and json_path.exists()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Status distribution" in markdown
    assert "New breaks" in markdown
    assert "Recovered" in markdown
    assert "Newly probed datasets" in markdown
    assert "Newly added datasets" in markdown
    assert "Schema and record-count changes" in markdown
    snapshot = json.loads(json_path.read_text(encoding="utf-8"))
    assert snapshot["week"] == FAKE_DATE
    assert [row["dataset_id"] for row in snapshot["changes"]["recovered"]] == ["beta"]
    assert [row["dataset_id"] for row in snapshot["changes"]["newly_probed"]] == ["gamma"]
    assert [row["dataset_id"] for row in snapshot["changes"]["added"]] == ["gamma"]


def test_status_distribution_percentages_sum_to_100(tmp_path: Path) -> None:
    _, json_path = _run(_make_repo(tmp_path))
    distribution = json.loads(json_path.read_text(encoding="utf-8"))["status_distribution"]

    assert abs(sum(distribution["percentages"].values()) - 100) <= 0.5


def test_idempotent_second_run(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    paths = _run(repo)
    first = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    paths = _run(repo)

    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths] == first


def test_handles_short_history(tmp_path: Path) -> None:
    markdown_path, json_path = _run(_make_repo(tmp_path, short_history=True))
    snapshot = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert snapshot["changes"] == {}
    assert snapshot["caveats"]["history"] == "No comparable baseline available."
    assert "## Recovered" in markdown
    assert "## Newly probed datasets" in markdown
    assert "## Newly added datasets" in markdown
    assert markdown.count("_No comparable baseline available._") >= 3


def test_reproducibility_footer_present(tmp_path: Path) -> None:
    markdown_path, _ = _run(_make_repo(tmp_path))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert "## Reproducibility" in markdown
    assert "https://data-pulse.my/trust-snapshot-2026-08-09.md" in markdown
