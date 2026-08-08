#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture="$(mktemp)"
trap 'rm -f "$fixture"' EXIT

DATAPULSE_CHECK_SOURCE_ONLY=true source "$repo_root/scripts/check.sh"

assert_metrics() {
  local expected_compatible="$1"
  local expected_legacy="$2"
  local expected_transition="$3"
  local expected_invalid="$4"
  local metrics

  metrics="$(extract_npra_registration_format_metrics "$fixture")"
  jq -e \
    --argjson compatible "$expected_compatible" \
    --argjson legacy "$expected_legacy" \
    --argjson transition "$expected_transition" \
    --argjson invalid "$expected_invalid" \
    '.registration_format_compatible == $compatible
      and .legacy_registration_count == $legacy
      and .transition_registration_count == $transition
      and .invalid_registration_count == $invalid' \
    <<< "$metrics" >/dev/null
}

printf '%s\n' \
  'reg_no,product' \
  'MAL19913374AZ,Legacy product' \
  'mal19973272T,Legacy lowercase source value' \
  'MAL + 12345678 + X,Transition product' \
  'MAL 87654321 TC,Transition product without plus signs' \
  > "$fixture"
assert_metrics true 2 2 0

printf '%s\n' \
  'reg_no,product' \
  'MAL19913374AZ,Legacy product' \
  'NOT-A-REGISTRATION,Invalid product' \
  > "$fixture"
assert_metrics false 1 0 1

{
  printf '<html><body>\n'
  for appendix in {1..12}; do
    printf '<a href="appendix-%s.pdf">Appendix %s</a>\n' "$appendix" "$appendix"
  done
  printf '<a href="duplicate.pdf">Appendix 12</a>\n'
  printf '</body></html>\n'
} > "$fixture"
guidance_metrics="$(extract_npra_guidance_metrics "$fixture")"
jq -e '.guidance_structure_compatible == true and .appendix_resource_count == 12' \
  <<< "$guidance_metrics" >/dev/null

printf '<a>Appendix 11</a>\n' > "$fixture"
guidance_metrics="$(extract_npra_guidance_metrics "$fixture")"
jq -e '.guidance_structure_compatible == false and .appendix_resource_count == 1' \
  <<< "$guidance_metrics" >/dev/null

printf 'NPRA probe tests passed.\n'
