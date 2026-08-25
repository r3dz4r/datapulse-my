#!/usr/bin/env bash
#
# DataPulse MY generation profiles.
#
# health-cycle: 14 steps for artifacts derived from the live health snapshot.
# release-build: validated deterministic generation for the complete public-site artifact set.
#
# This script orchestrates local artifact generation in reviewed order.
# It never commits, pushes, or deploys; release-build embeds dashboard data locally.
#
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/generate.sh <profile> [--list] [--env KEY=VAL]
       ./scripts/generate.sh --list-owned-outputs <profile>
       ./scripts/generate.sh --list-runtime-ownership <profile>

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

list_owned_outputs=false
list_runtime_ownership=false
if [[ "$1" == "--list-owned-outputs" || "$1" == "--list-runtime-ownership" ]]; then
  if (( $# != 2 )); then
    printf 'generate.sh: %s requires one profile\n' "$1" >&2
    exit 2
  fi
  if [[ "$1" == "--list-owned-outputs" ]]; then
    list_owned_outputs=true
  else
    list_runtime_ownership=true
  fi
  profile="$2"
  shift 2
else
  profile="$1"
  shift
fi

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
      "gen_trends.py"
      "gen_drift.py"
      "gen_reconciliation.py"
      "gen_attestations.py"
      "gen_dataset_deltas.py"
      "gen_record_evidence.py"
      "gen_evidence_coverage.py"
      "gen_catalog_graph.py"
    )
    outputs=(
      "data/<id>.md"
      "badges/<id>.svg; badges/status-*.svg; badges/index.svg"
      "README.md (dataset counts and trust-summary block)"
      "feed.xml"
      "catalog-snapshot.json; changelog.json (deprecated alias)"
      "health/history.jsonl; health/history_daily.json"
      "health/trends.json"
      "health/drift.json"
      "health/reconciliation.json"
      "attestations/<date>/{<id>.json,index.json,chain_head.json,binding.json,scores.json}; attestations/latest/*; datapulse.json attestation_ref/methodology_version"
      "deltas/<cycle>.json"
      "record-evidence/<vertical-id>/<run-date>.json; record-evidence/<vertical-id>/latest.json (opt-in)"
      "health/evidence-coverage.json"
      "catalog-graph.json"
    )
    ;;
  release-build)
    description="Regenerate health-cycle plus public discovery, JSON-LD, MCP, envelope, and dashboard artifacts."
    generators=(
      "bump_mcp_source_version.py"
      "public_surface_preflight"
      "gen_mcp_reference.py"
      "gen_llms_summary.py"
      "gen_public_discovery.py"
      "gen_dashboard_sections.py"
      "gen_data_reports.sh"
      "gen_health_methodology.py"
      "gen_badges.sh"
      "gen_readme_summary.sh"
      "gen_rss.sh"
      "gen_catalog_snapshot.py"
      "gen_health_history.py"
      "gen_trends.py"
      "gen_drift.py"
      "gen_reconciliation.py"
      "gen_attestations.py"
      "gen_dataset_deltas.py"
      "gen_record_evidence.py"
      "gen_evidence_coverage.py"
      "gen_catalog_graph.py"
      "gen_json_envelope.py"
      "gen_jsonld_catalog.py"
      "gen_dashboard_filters.py"
      "embed_dashboard_data.py"
      "gen_api_reference.py"
      "check_url_drift.py"
      "gen_trust_snapshot.py"
      "gen_health_methodology_html.py"
      "gen_site_nav.py"
    )
    outputs=(
      "mcp/server.py source identity and mcp.json provenance"
      "validation only (config, schemas, source identity, and all P5A markers)"
      "mcp.json; agent.json; docs/mcp-reference.md; llms.txt MCP tools block; README.md MCP tools block; docs/mcp-deploy.md MCP tools block"
      "llms.txt catalog-summary and featured-datasets blocks"
      "sitemap.xml; robots.txt public-discovery block; README.md public-discovery block; llms.txt public-discovery block"
      "docs/.dashboard_sections.json"
      "data/<id>.md"
      "docs/health-methodology.md"
      "badges/<id>.svg; badges/status-*.svg; badges/index.svg"
      "README.md (dataset counts, trust-summary block, and MCP tools block)"
      "feed.xml"
      "catalog-snapshot.json; changelog.json (deprecated alias)"
      "health/history.jsonl; health/history_daily.json"
      "health/trends.json"
      "health/drift.json"
      "health/reconciliation.json"
      "attestations/<date>/{<id>.json,index.json,chain_head.json,binding.json,scores.json}; attestations/latest/*; datapulse.json attestation_ref/methodology_version"
      "deltas/<cycle>.json"
      "record-evidence/<vertical-id>/<run-date>.json; record-evidence/<vertical-id>/latest.json (opt-in)"
      "health/evidence-coverage.json"
      "catalog-graph.json"
      "data/json/<id>.json"
      "data/jsonld/<id>.json; data/jsonld/catalog.json"
      "docs/.dashboard_filters.json"
      "docs/{index,npra}.html (embedded manifest, health, filters, sections, and marker-owned public facts)"
      "docs/buyer-api-reference.md (marked runtime-derived API blocks)"
      "URL drift and cadence audit"
      "docs/trust-snapshot-<date>.{md,json}"
      "docs/health-methodology.html"
      "docs/{index,landing,npra,health-methodology}.html site navigation"
    )
    ;;
  *)
    printf 'generate.sh: unknown profile: %s\n' "$profile" >&2
    printf 'Valid profiles: health-cycle, release-build\n' >&2
    exit 2
    ;;
esac

if [[ "$list_owned_outputs" == true ]]; then
  for output in "${outputs[@]}"; do
    printf '%s\n' "$output"
  done
  exit 0
fi

if [[ "$list_runtime_ownership" == true ]]; then
  python3 - "$profile" <<'PY'
import json
import sys
from pathlib import Path

profile = sys.argv[1]
scope = json.loads(Path("scripts/contract-scope.json").read_text(encoding="utf-8"))
records = scope.get("runtime_derived_surfaces", [])
if not isinstance(records, list):
    raise SystemExit("generate.sh: runtime ownership contract is malformed")
owned = [record for record in records if profile in record.get("profiles", [])]
print(json.dumps(owned, ensure_ascii=False, indent=2, sort_keys=True))
PY
  exit 0
fi

printf 'Profile: %s\n' "$profile"
printf 'Purpose: %s\n' "$description"

command_for() {
  case "$1" in
    public_surface_preflight) printf 'python3 scripts/gen_mcp_reference.py --validate-only && python3 scripts/gen_llms_summary.py --validate-only && python3 scripts/gen_public_discovery.py --validate-only' ;;
    *.sh)
      printf 'DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" bash scripts/%s' "$1"
      ;;
    gen_json_envelope.py) printf 'python3 scripts/%s --force' "$1" ;;
    gen_health_history.py) printf 'python3 scripts/%s --compact' "$1" ;;
    gen_attestations.py) printf 'DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE=... python3 scripts/%s --private-key "$DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE"' "$1" ;;
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
    public_surface_preflight)
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" env "${environment[@]}" python3 scripts/gen_mcp_reference.py --validate-only
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" env "${environment[@]}" python3 scripts/gen_llms_summary.py --validate-only
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" env "${environment[@]}" python3 scripts/gen_public_discovery.py --validate-only
      ;;
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
      if [[ -z "${DATAPULSE_ARCHIVES_DIR:-}" ]]; then
        if [[ -d /home/redza/runtime && -w /home/redza/runtime ]]; then
          DATAPULSE_ARCHIVES_DIR=/home/redza/runtime/datapulse-history
        else
          DATAPULSE_ARCHIVES_DIR="${DATAPULSE_REPO_ROOT:-$PWD}/.archives"
        fi
      fi
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" \
        env "${environment[@]}" \
        python3 "scripts/$generator" --compact --retention-days 7 \
          --archives-dir "$DATAPULSE_ARCHIVES_DIR"
      ;;
    gen_attestations.py)
      if [[ -z "${DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE:-}" ]]; then
        if [[ -f docs/.well-known/datapulse-probe-keys.json ]]; then
          printf 'set DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE for attestation generation\n' >&2
          exit 1
        fi
        printf 'attestation generation skipped: no published key registry in this fixture\n'
        continue
      fi
      attestation_args=(--private-key "$DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE")
      if [[ -n "${DATAPULSE_SIGSTORE_REKOR_REFERENCE:-}" ]]; then
        attestation_args+=(--rekor-reference "$DATAPULSE_SIGSTORE_REKOR_REFERENCE")
      fi
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" env "${environment[@]}" \
        python3 "scripts/$generator" "${attestation_args[@]}"
      ;;
    *.py)
      DATAPULSE_REPO_ROOT="${DATAPULSE_REPO_ROOT:-$PWD}" \
        env "${environment[@]}" \
        python3 "scripts/$generator"
      ;;
  esac
done
