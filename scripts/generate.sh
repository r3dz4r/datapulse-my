#!/usr/bin/env bash
#
# DataPulse MY generation profiles.
#
# health-cycle: 7 steps for artifacts derived from the live health snapshot.
# release-build: source stamp plus 15 steps for the complete public-site artifact set.
#
# This script orchestrates local artifact generation in reviewed order.
# It never commits, pushes, or deploys; release-build embeds dashboard data locally.
#
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/generate.sh <profile> [--list] [--env KEY=VAL]

Profiles:
  health-cycle   Regenerate artifacts derived from a fresh health/latest.json.
  release-build  Regenerate health-cycle plus public discovery artifacts.

Options:
  --list         Print ordered commands and owned paths without running them.
  --env KEY=VAL  Pass an environment variable to each generator command.
  --help         Show this help message.
EOF
}

if (( $# == 0 )); then
  usage
  exit 0
fi

profile="$1"
shift

if [[ "$profile" == "--help" || "$profile" == "-h" ]]; then
  usage
  exit 0
fi

list_only=false
environment=()
while (( $# > 0 )); do
  case "$1" in
    --list)
      list_only=true
      shift
      ;;
    --env)
      if (( $# < 2 )) || [[ "$2" != *=* ]]; then
        printf 'generate.sh: --env requires KEY=VAL\n' >&2
        exit 2
      fi
      key="${2%%=*}"
      if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        printf 'generate.sh: invalid environment key: %s\n' "$key" >&2
        exit 2
      fi
      environment+=("$2")
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'generate.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

case "$profile" in
  health-cycle)
    description="Regenerate artifacts derived from a fresh health/latest.json after a health check."
    generators=(
      "gen_data_reports.sh"
      "gen_badges.sh"
      "gen_readme_summary.sh"
      "gen_rss.sh"
      "gen_catalog_snapshot.py"
      "gen_health_history.py"
      "gen_dataset_deltas.py"
    )
    outputs=(
      "data/<id>.md"
      "badges/<id>.svg; badges/status-*.svg; badges/index.svg"
      "README.md (dataset counts and trust-summary block)"
      "feed.xml"
      "catalog-snapshot.json; changelog.json (deprecated alias)"
      "health/history.jsonl; health/history_daily.json"
      "deltas/<cycle>.json"
    )
    ;;
  release-build)
    description="Regenerate health-cycle plus public discovery, JSON-LD, MCP, envelope, and dashboard artifacts."
    generators=(
      "bump_mcp_source_version.py"
      "gen_dashboard_sections.py"
      "gen_data_reports.sh"
      "gen_badges.sh"
      "gen_readme_summary.sh"
      "gen_llms_summary.py"
      "gen_rss.sh"
      "gen_catalog_snapshot.py"
      "gen_health_history.py"
      "gen_dataset_deltas.py"
      "gen_json_envelope.py"
      "gen_jsonld_catalog.py"
      "gen_mcp_reference.py"
      "gen_dashboard_filters.py"
      "embed_dashboard_data.py"
      "check_url_drift.py"
      "gen_trust_snapshot.py"
    )
    outputs=(
      "mcp/server.py (SOURCE_COMMIT_SHA/SOURCE_COMMIT_DATE constants); mcp.json (source_commit_sha/source_commit_date fields)"
      "docs/.dashboard_sections.json"
      "data/<id>.md"
      "badges/<id>.svg; badges/status-*.svg; badges/index.svg"
      "README.md (dataset counts and trust-summary block)"
      "llms.txt (dataset-count references only)"
      "feed.xml"
      "catalog-snapshot.json; changelog.json (deprecated alias)"
      "health/history.jsonl; health/history_daily.json"
      "deltas/<cycle>.json"
      "data/json/<id>.json"
      "data/jsonld/<id>.json; data/jsonld/catalog.json"
      "docs/mcp-reference.md; mcp.json"
      "docs/.dashboard_filters.json"
      "docs/index.html (embedded manifest, health, filters, and sections)"
      "URL drift and cadence audit"
      "docs/trust-snapshot-<date>.{md,json}"
    )
    ;;
  *)
    printf 'generate.sh: unknown profile: %s\n' "$profile" >&2
    printf 'Valid profiles: health-cycle, release-build\n' >&2
    exit 2
    ;;
esac

printf 'Profile: %s\n' "$profile"
printf 'Purpose: %s\n' "$description"

command_for() {
  case "$1" in
    *.sh)
      printf 'DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" bash scripts/%s' "$1"
      ;;
    gen_json_envelope.py) printf 'python3 scripts/%s --force' "$1" ;;
    gen_health_history.py) printf 'python3 scripts/%s --compact' "$1" ;;
    *.py) printf 'python3 scripts/%s' "$1" ;;
  esac
}

if [[ "$list_only" == true ]]; then
  for index in "${!generators[@]}"; do
    if [[ "$profile" == "release-build" ]]; then
      step_number="$index"
    else
      step_number="$((index + 1))"
    fi
    printf '%d. ' "$step_number"
    command_for "${generators[$index]}"
    printf '\n   owns: %s\n' "${outputs[$index]}"
  done
  exit 0
fi

for index in "${!generators[@]}"; do
  generator="${generators[$index]}"
  if [[ "$profile" == "release-build" ]]; then
    step_number="$index"
    final_step="$((${#generators[@]} - 1))"
  else
    step_number="$((index + 1))"
    final_step="${#generators[@]}"
  fi
  printf 'Step %d/%d: ' "$step_number" "$final_step"
  command_for "$generator"
  printf '\n'

  case "$generator" in
    *.sh)
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" \
        env "${environment[@]}" \
        bash "scripts/$generator"
      ;;
    gen_json_envelope.py)
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" \
        env "${environment[@]}" \
        python3 "scripts/$generator" --force
      ;;
    gen_health_history.py)
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" \
        env "${environment[@]}" \
        python3 "scripts/$generator" --compact
      ;;
    *.py)
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" \
        env "${environment[@]}" \
        python3 "scripts/$generator"
      ;;
  esac
done
