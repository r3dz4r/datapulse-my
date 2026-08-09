#!/usr/bin/env bash
#
# DataPulse MY generation profiles.
#
# health-cycle: 5 steps for artifacts derived from the live health snapshot.
# release-build: 9 steps for the complete public-site artifact set.
#
# This script orchestrates local artifact generation in reviewed order.
# It never commits, pushes, deploys, or performs the dashboard HTML embed step.
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
      "gen_changelog.py"
    )
    outputs=(
      "data/<id>.md"
      "badges/<id>.svg; badges/status-*.svg; badges/index.svg"
      "README.md (trust-summary block only)"
      "feed.xml"
      "changelog.json"
    )
    ;;
  release-build)
    description="Regenerate health-cycle plus public discovery, JSON-LD, MCP, envelope, and filter artifacts."
    generators=(
      "gen_data_reports.sh"
      "gen_badges.sh"
      "gen_readme_summary.sh"
      "gen_rss.sh"
      "gen_changelog.py"
      "gen_json_envelope.py"
      "gen_jsonld_catalog.py"
      "gen_mcp_reference.py"
      "gen_dashboard_filters.py"
    )
    outputs=(
      "data/<id>.md"
      "badges/<id>.svg; badges/status-*.svg; badges/index.svg"
      "README.md (trust-summary block only)"
      "feed.xml"
      "changelog.json"
      "data/json/<id>.json"
      "data/jsonld/<id>.json; data/jsonld/catalog.json"
      "docs/mcp-reference.md; mcp.json"
      "docs/.dashboard_filters.json"
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
    *.py) printf 'python3 scripts/%s' "$1" ;;
  esac
}

if [[ "$list_only" == true ]]; then
  for index in "${!generators[@]}"; do
    printf '%d. ' "$((index + 1))"
    command_for "${generators[$index]}"
    printf '\n   owns: %s\n' "${outputs[$index]}"
  done
  exit 0
fi

for index in "${!generators[@]}"; do
  generator="${generators[$index]}"
  printf 'Step %d/%d: ' "$((index + 1))" "${#generators[@]}"
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
    *.py)
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" \
        env "${environment[@]}" \
        python3 "scripts/$generator"
      ;;
  esac
done
