import json
from pathlib import Path
import shutil
import subprocess


REPO_ROOT = Path(__file__).parents[2]
STATUSES = (
    "fresh",
    "aging",
    "stale",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
    "reference",
)


def test_generator_emits_all_status_badges_including_zero_counts(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    for name in ("gen_badges.sh", "gen_status_legend.sh"):
        source = REPO_ROOT / "scripts" / name
        destination = scripts_dir / name
        shutil.copy2(source, destination)

    health_path = tmp_path / "health.json"
    health_path.write_text(
        json.dumps(
            {
                "_trust_summary": {
                    "by_status": {
                        "fresh": 1,
                        "aging": 1,
                        "stale": 1,
                        "degraded": 0,
                        "browser_dependent": 1,
                        "unreachable": 1,
                        "unknown": 0,
                        "unknown_freshness": 1,
                        "reference": 1,
                    }
                },
                "datasets": [
                    {"dataset_id": "alpha", "status": "fresh"},
                ],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        ["bash", "scripts/gen_badges.sh", str(health_path)],
        cwd=tmp_path,
        check=True,
    )

    for status in STATUSES:
        badge = tmp_path / "badges" / f"status-{status}.svg"
        assert badge.exists(), f"missing aggregate badge for {status}"
