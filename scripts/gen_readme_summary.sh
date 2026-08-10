#!/usr/bin/env bash
set -euo pipefail

health_file="${1:-health/latest.json}"
readme_file="README.md"
marker='Current distribution (`_trust_summary`):'

if ! command -v jq >/dev/null 2>&1; then
  printf 'jq is required\n' >&2
  exit 1
fi

if [[ ! -r "$health_file" ]]; then
  printf 'Cannot read health summary: %s\n' "$health_file" >&2
  exit 1
fi

if [[ ! -r "$readme_file" ]]; then
  printf 'Cannot read README: %s\n' "$readme_file" >&2
  exit 1
fi

if ! summary="$(jq -er '
  ._trust_summary.by_status as $counts
  | if ($counts | type) != "object" then
      error("._trust_summary.by_status must be an object")
    else
      [
        {key: "fresh", label: "fresh"},
        {key: "aging", label: "aging"},
        {key: "stale", label: "stale"},
        {key: "degraded", label: "degraded"},
        {key: "browser_dependent", label: "browser-dependent"},
        {key: "unreachable", label: "unreachable"},
        {key: "unknown", label: "unknown"},
        {key: "unknown_freshness", label: "unknown-freshness"},
        {key: "reference", label: "reference"}
      ]
      | map(. + {count: ($counts[.key] // 0)})
      | if all(.[]; (.count | type == "number" and . >= 0 and floor == .)) then
          map(select(.count > 0))
          | map("[\(.count) \(.label)](badges/status-\(.label).svg)")
          | "Current distribution (`_trust_summary`): " + join(" · ")
        else
          error("trust-summary status counts must be non-negative integers")
        end
    end
' "$health_file")"; then
  printf 'Invalid trust summary: %s\n' "$health_file" >&2
  exit 1
fi

if ! dataset_total="$(jq -er '
  ._trust_summary.datasets_total
  | select(type == "number" and . >= 0 and floor == .)
' "$health_file")"; then
  printf 'Invalid dataset total: %s\n' "$health_file" >&2
  exit 1
fi

tmp_file="$(mktemp "${readme_file}.tmp.XXXXXX")"
trap 'rm -f "$tmp_file"' EXIT
chmod --reference="$readme_file" "$tmp_file"

if ! awk -v marker="$marker" -v summary="$summary" -v dataset_total="$dataset_total" '
  !replacing && index($0, marker) == 1 {
    print summary
    replacing = 1
    found = 1
    next
  }
  replacing {
    if ($0 == "") {
      print
      replacing = 0
    }
    next
  }
  {
    gsub(/[0-9]+ official/, dataset_total " official")
    gsub(/[0-9]+-dataset catalogue/, dataset_total "-dataset catalogue")
    print
  }
  END {
    if (!found || replacing) exit 1
  }
' "$readme_file" > "$tmp_file"; then
  printf 'Could not replace trust summary block in %s\n' "$readme_file" >&2
  exit 1
fi

if cmp -s "$tmp_file" "$readme_file"; then
  exit 0
fi

mv "$tmp_file" "$readme_file"
trap - EXIT
