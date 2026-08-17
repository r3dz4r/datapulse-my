"""Integration tests for the named artifact-generation profiles."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from scripts.tests.generator_harness import (
    GeneratorRun,
    run_generator,
    run_generator_twice,
)

ROOT = Path(__file__).resolve().parents[2]
MINIMAL_FIXTURE = ROOT / "scripts/tests/fixtures/generator/minimal"
HEALTH_FIXTURE = (
    ROOT / "scripts/tests/fixtures/repository_contract/valid/health/latest.json"
)
RELEASE_FIXTURE = ROOT / "scripts/tests/fixtures/generator/python_release"
SHELL_FIXTURE = ROOT / "scripts/tests/fixtures/generator/shell"
GENERATORS = (
    "bump_mcp_source_version.py",
    "gen_data_reports.sh",
    "gen_badges.sh",
    "gen_status_legend.sh",
    "gen_readme_summary.sh",
    "gen_llms_summary.py",
    "gen_rss.sh",
    "gen_catalog_snapshot.py",
    "gen_health_history.py",
    "gen_trends.py",
    "gen_drift.py",
    "gen_reconciliation.py",
    "gen_dataset_deltas.py",
    "gen_record_evidence.py",
    "gen_catalog_graph.py",
    "gen_trust_snapshot.py",
    "gen_json_envelope.py",
    "gen_jsonld_catalog.py",
    "gen_mcp_reference.py",
    "gen_dashboard_filters.py",
    "gen_dashboard_sections.py",
    "embed_dashboard_data.py",
    "check_url_drift.py",
    "gen_health_methodology_html.py",
    "gen_health_methodology.py",
    "gen_site_nav.py",
    "gen_health_methodology_content.py",
    "health_policy.py",
    "check.sh",
)
HEALTH_STEPS = (
    "gen_data_reports.sh",
    "gen_badges.sh",
    "gen_readme_summary.sh",
    "gen_rss.sh",
    "gen_catalog_snapshot.py",
    "gen_health_history.py",
    "gen_trends.py",
    "gen_drift.py",
    "gen_reconciliation.py",
    "gen_dataset_deltas.py",
    "gen_record_evidence.py",
    "gen_catalog_graph.py",
)
RELEASE_STEPS = (
    "gen_dashboard_sections.py",
    "gen_data_reports.sh",
    "gen_health_methodology.py",
    "gen_badges.sh",
    "gen_readme_summary.sh",
    "gen_llms_summary.py",
    "gen_rss.sh",
    "gen_catalog_snapshot.py",
    "gen_health_history.py",
    "gen_trends.py",
    "gen_drift.py",
    "gen_reconciliation.py",
    "gen_dataset_deltas.py",
    "gen_record_evidence.py",
    "gen_catalog_graph.py",
    "gen_json_envelope.py",
    "gen_jsonld_catalog.py",
    "gen_mcp_reference.py",
    "gen_dashboard_filters.py",
    "embed_dashboard_data.py",
    "check_url_drift.py",
    "gen_trust_snapshot.py",
    "gen_health_methodology_html.py",
    "gen_site_nav.py",
)
HEALTH_OUTPUTS = (
    "README.md",
    "feed.xml",
    "badges/alpha.svg",
    "badges/status-fresh.svg",
    "changelog.json",
    "catalog-snapshot.json",
    "health/history.jsonl",
    "health/history_daily.json",
    "health/trends.json",
    "health/drift.json",
    "health/reconciliation.json",
    "deltas/2026-08-08T00:00.json",
    "catalog-graph.json",
)
RELEASE_OUTPUTS = HEALTH_OUTPUTS + (
    "llms.txt",
    "data/json/alpha.json",
    "data/jsonld/alpha.json",
    "data/jsonld/catalog.json",
    "docs/mcp-reference.md",
    "mcp.json",
    "agent.json",
    "docs/mcp-deploy.md",
    "docs/.dashboard_filters.json",
    "docs/.dashboard_sections.json",
    "docs/index.html",
    "docs/health-methodology.html",
)
PROFILE_INPUTS = (
    ".git",
    "datapulse.json",
    "reconciliation_groups.json",
    "health",
    "README.md",
    "llms.txt",
    "docs",
    "agent.json",
    "mcp.json",
    "mcp",
    "scripts",
    ".cache",
)


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _stage_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    shutil.copytree(MINIMAL_FIXTURE, source)

    manifest = json.loads((source / "datapulse.json").read_text(encoding="utf-8"))
    for row in manifest["datasets"]:
        dataset_id = row["id"]
        row.update(
            {
                "name": f"{dataset_id.title()} Dataset",
                "namespace": "other",
                "licence": "CC BY 4.0",
                "real_status": "active",
                "steward": "Fixture Agency",
                "source": "Fixture Portal",
                "url": f"data:text/csv,name%0A{dataset_id}",
                "geo_coverage": "Malaysia",
                "health_report": f"data/{dataset_id}.md",
                "refresh_frequency": "daily",
            }
        )
    _write_json(source / "datapulse.json", manifest)
    _write_json(source / "reconciliation_groups.json", {"schema": "datapulse/v1/reconciliation-groups", "groups": []})

    health = json.loads(HEALTH_FIXTURE.read_text(encoding="utf-8"))
    for row in health["datasets"]:
        dataset_id = row["dataset_id"]
        row.update(
            {
                "last_checked": health["checked_at"],
                "message": "Fixture health result.",
                "http_status": 200,
                "record_count": 1,
                "url": f"data:text/csv,name%0A{dataset_id}",
            }
        )
    _write_json(source / "health/latest.json", health)
    checked_at = health["checked_at"]
    history_observed_at = (
        datetime.fromisoformat(checked_at.replace("Z", "+00:00")) + timedelta(days=8)
    ).isoformat().replace("+00:00", "Z")
    sample_dataset_id = manifest["datasets"][0]["id"]
    history_row = {
        "dataset_id": sample_dataset_id,
        "observed_at": history_observed_at,
        "cycle": history_observed_at[:16],
        "status": "fresh",
        "freshness_signal": "content-date-parse",
        "last_modified": history_observed_at,
        "content_date": history_observed_at[:10],
        "record_count": 1,
        "record_count_estimated": False,
        "http_status": 200,
        "probe_outcome": "success",
        "message": "Fixture history row.",
    }
    (source / "health/history.jsonl").write_text(
        json.dumps(history_row, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    shutil.copy2(SHELL_FIXTURE / "README.md", source / "README.md")
    with (source / "README.md").open("a", encoding="utf-8") as output:
        output.write(
            "\n<!-- BEGIN mcp-tools -->\n"
            "- 0 tools:\n\n"
            "The public endpoint is live and serves all 0 read-only tools over the\n"
            "0-dataset catalogue.\n"
            "<!-- END mcp-tools -->\n"
        )
    (source / "llms.txt").write_text(
        "> a machine-readable manifest of 42 official datasets\n"
        "Agents can query the 42-dataset catalogue natively.\n"
        "The endpoint serves tools over the 42-dataset catalogue.\n\n"
        "<!-- BEGIN mcp-tools -->\n"
        "### Tools\n\n"
        "| Tool | Use when |\n|---|---|\n"
        "<!-- END mcp-tools -->\n",
        encoding="utf-8",
    )
    (source / "docs").mkdir()
    (source / "docs/assets").mkdir()
    shutil.copy2(ROOT / "docs/assets/site-nav.html", source / "docs/assets/site-nav.html")
    shutil.copy2(RELEASE_FIXTURE / "docs/index.html", source / "docs/index.html")
    shutil.copy2(
        RELEASE_FIXTURE / "docs/health-methodology.md",
        source / "docs/health-methodology.md",
    )
    shutil.copy2(
        RELEASE_FIXTURE / "docs/mcp-reference.md",
        source / "docs/mcp-reference.md",
    )
    shutil.copy2(RELEASE_FIXTURE / "mcp.json", source / "mcp.json")
    shutil.copy2(RELEASE_FIXTURE / "agent.json", source / "agent.json")
    shutil.copy2(RELEASE_FIXTURE / "docs/mcp-deploy.md", source / "docs/mcp-deploy.md")
    shutil.copytree(RELEASE_FIXTURE / "mcp", source / "mcp")

    metrics_cache = source / ".cache/datapulse/metrics_dataset_cumul.json"
    _write_json(
        metrics_cache,
        {
            "fetched_at": "2999-01-01T00:00:00Z",
            "datasets": [
                {"id": row["id"], "views": index + 1}
                for index, row in enumerate(manifest["datasets"])
            ],
        },
    )

    scripts = source / "scripts"
    scripts.mkdir()
    shutil.copytree(ROOT / "scripts/templates", scripts / "templates")
    shutil.copy2(ROOT / "scripts/generate.sh", scripts / "generate.sh")
    for generator in GENERATORS:
        shutil.copy2(ROOT / "scripts" / generator, scripts / generator)
    shutil.copy2(ROOT / "scripts/gen_anomaly.py", scripts / "gen_anomaly.py")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=source,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=source, check=True)
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=source, check=True)
    return source


def _runner(tmp_path: Path, *arguments: str) -> Path:
    name = "-".join(arg.lstrip("-") for arg in arguments)
    runner = tmp_path / f"runner-{name}.sh"
    command = " ".join(arguments)
    runner.write_text(
        f"#!/usr/bin/env bash\nset -euo pipefail\nbash scripts/generate.sh {command}\n",
        encoding="utf-8",
    )
    runner.chmod(0o755)
    return runner


def _run_profile(
    tmp_path: Path,
    profile: str,
    *,
    list_mode: bool = False,
    outputs: tuple[str, ...] = (),
    source: Path | None = None,
) -> GeneratorRun:
    source = source or _stage_source(tmp_path)
    arguments = (profile, "--list") if list_mode else (profile,)
    return run_generator(
        source,
        _runner(tmp_path, *arguments),
        list(PROFILE_INPUTS),
        list(outputs),
    )


def test_health_cycle_lists_twelve_steps(tmp_path: Path) -> None:
    result = _run_profile(tmp_path, "health-cycle", list_mode=True)

    assert result.returncode == 0, result.stderr
    for step in HEALTH_STEPS:
        assert step in result.stdout


def test_release_build_lists_all_twenty_one_steps(tmp_path: Path) -> None:
    result = _run_profile(tmp_path, "release-build", list_mode=True)

    assert result.returncode == 0, result.stderr
    for step in RELEASE_STEPS:
        assert step in result.stdout


def test_record_evidence_runs_immediately_after_deltas(tmp_path: Path) -> None:
    result = _run_profile(tmp_path, "health-cycle", list_mode=True)

    assert result.returncode == 0, result.stderr
    assert (
        result.stdout.index("gen_dataset_deltas.py")
        < result.stdout.index("gen_record_evidence.py")
        < result.stdout.index("gen_catalog_graph.py")
    )


def test_trends_drift_and_reconciliation_run_immediately_after_history(tmp_path: Path) -> None:
    result = _run_profile(tmp_path, "health-cycle", list_mode=True)

    assert result.returncode == 0, result.stderr
    assert result.stdout.index("gen_health_history.py") < result.stdout.index("gen_trends.py")
    assert result.stdout.index("gen_trends.py") < result.stdout.index("gen_drift.py")
    assert result.stdout.index("gen_drift.py") < result.stdout.index("gen_reconciliation.py")
    assert result.stdout.index("gen_reconciliation.py") < result.stdout.index("gen_dataset_deltas.py")


def test_health_cycle_runs_in_clean_fixture(tmp_path: Path) -> None:
    result = _run_profile(tmp_path, "health-cycle", outputs=HEALTH_OUTPUTS)

    assert result.returncode == 0, result.stderr
    assert all(result.outputs[path] is not None for path in HEALTH_OUTPUTS)


def test_release_build_runs_in_clean_fixture(tmp_path: Path) -> None:
    result = _run_profile(tmp_path, "release-build", outputs=RELEASE_OUTPUTS)

    assert result.returncode == 0, result.stderr
    assert all(result.outputs[path] is not None for path in RELEASE_OUTPUTS)
    dashboard = result.outputs["docs/index.html"].decode("utf-8")
    assert dashboard.count("<!-- BEGIN changelog-strip -->") == 1
    assert dashboard.count("<!-- END changelog-strip -->") == 1
    dataset_count = len(
        json.loads((result.workdir / "datapulse.json").read_text(encoding="utf-8"))["datasets"]
    )
    assert f"{dataset_count} datasets tracked" in dashboard
    assert 'href="/health/latest.json"' in dashboard
    archives = list((result.workdir / ".archives").glob("health-*.jsonl.gz"))
    assert archives, "release-build must archive expired history inside its workdir"


def test_unknown_profile_exits_nonzero(tmp_path: Path) -> None:
    result = _run_profile(tmp_path, "nonexistent")

    assert result.returncode != 0
    assert "unknown profile" in result.stderr.lower()


def test_deterministic_second_run(tmp_path: Path) -> None:
    source = _stage_source(tmp_path)
    first, second, diff = run_generator_twice(
        source,
        _runner(tmp_path, "health-cycle"),
        list(PROFILE_INPUTS),
        list(HEALTH_OUTPUTS),
    )

    assert first.returncode == second.returncode == 0, first.stderr or second.stderr
    assert all(diff.values())


def test_release_build_is_deterministic_on_second_run(tmp_path: Path) -> None:
    source = _stage_source(tmp_path)
    first, second, diff = run_generator_twice(
        source,
        _runner(tmp_path, "release-build"),
        list(PROFILE_INPUTS),
        list(RELEASE_OUTPUTS),
    )

    assert first.returncode == second.returncode == 0, first.stderr or second.stderr
    assert all(diff.values())


def test_stops_on_first_failure(tmp_path: Path) -> None:
    source = _stage_source(tmp_path)
    (source / "health/latest.json").write_text('{"checked_at":', encoding="utf-8")

    result = _run_profile(
        tmp_path,
        "health-cycle",
        source=source,
        outputs=("badges/alpha.svg", "feed.xml", "catalog-snapshot.json"),
    )

    assert result.returncode != 0
    assert all(output is None for output in result.outputs.values())


def test_does_not_push_or_deploy(tmp_path: Path) -> None:
    before = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    for profile in ("health-cycle", "release-build"):
        result = _run_profile(tmp_path / profile, profile)
        assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert after == before


def test_list_mode_does_not_execute_generators(tmp_path: Path) -> None:
    source = _stage_source(tmp_path)
    sentinel = source / "sentinel.txt"
    sentinel.write_text("untouched\n", encoding="utf-8")

    result = run_generator(
        source,
        _runner(tmp_path, "health-cycle", "--list"),
        [*PROFILE_INPUTS, "sentinel.txt"],
        [
            "data/alpha.md",
            "badges/alpha.svg",
            "feed.xml",
            "catalog-snapshot.json",
            "sentinel.txt",
        ],
    )

    assert result.returncode == 0, result.stderr
    assert result.outputs["sentinel.txt"] == b"untouched\n"
    assert all(
        result.outputs[path] is None
        for path in (
            "data/alpha.md",
            "badges/alpha.svg",
            "feed.xml",
            "catalog-snapshot.json",
        )
    )


def test_help_message_includes_both_profiles(tmp_path: Path) -> None:
    result = _run_profile(tmp_path, "--help")

    assert result.returncode == 0, result.stderr
    assert "health-cycle" in result.stdout
    assert "release-build" in result.stdout
