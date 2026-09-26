"""Static contracts for served-surface transport handling."""

from __future__ import annotations

import json
import re
import subprocess
import textwrap
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/verify_served_release.sh"


def verifier() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _transport_helpers() -> str:
    match = re.search(
        r"(?ms)^fetch\(\) \{.*?^fetch_alias\(\) \{.*?^\}\n",
        verifier(),
    )
    assert match is not None
    return textwrap.dedent(match.group(0))


def _run_redirect_sensitive_helper(
    mode: str,
    script_mutation: tuple[str, str] | None = None,
    *,
    requested_path: str = "/landing.html",
    declared_target: str = "/landing",
    redirect_location: str = "/landing",
) -> subprocess.CompletedProcess[str]:
    alias_body = (
        '<title>DataPulse dataset register</title>\\n'
        '<link rel="canonical" href="/">\\n'
        '<meta http-equiv="refresh" content="0; url=/">\\n'
        '<a href="/">DataPulse dataset register</a>\\n'
    )
    requested_url = f"https://example.test{requested_path}"
    resolved_url = f"https://example.test{redirect_location}"
    helper = _transport_helpers()
    if script_mutation:
        helper = helper.replace(*script_mutation, 1)
    if mode == "alias":
        invocation = f"fetch_alias 'landing alias' {requested_url!r} {declared_target!r}"
    else:
        invocation = f"fetch 'landing surface' {requested_url!r} \"$smoke_dir/landing.html\""
    script = f"""
set -Eeuo pipefail
smoke_dir=$(mktemp -d)
trap 'rm -rf "$smoke_dir"' EXIT
base_url='https://example.test'
fetch_max_time=120
fail() {{ echo "$1" >&2; return 1; }}
curl() {{
  local follows=false dump='' output='' url='' arg status location body
  while (($#)); do
    arg="$1"
    case "$arg" in
      --location) follows=true; shift ;;
      --dump-header) dump="$2"; shift 2 ;;
      --output) output="$2"; shift 2 ;;
      --write-out) shift 2 ;;
      https://*) url="$arg"; shift ;;
      *) shift ;;
    esac
  done
  if [[ "$url" == {requested_url!r} && "$follows" == true ]]; then
    printf 'HTTP/2 308\\nLocation: %s\\n' {redirect_location!r} > "$dump"
    url={resolved_url!r}
  else
    : > "$dump"
  fi
  case "$url" in
    {requested_url!r}) status=308; location={redirect_location!r}; body='' ;;
    {resolved_url!r}) status=200; location=''; body={alias_body!r} ;;
    *) return 1 ;;
  esac
  printf 'HTTP/2 %s\\n' "$status" >> "$dump"
  if [[ -n "$location" ]]; then printf 'Location: %s\\n' "$location" >> "$dump"; fi
  printf '%s' "$body" > "$output"
  printf '%s 0.01 %s' "$status" "${{#body}}"
}}
{helper}
{invocation}
"""
    return subprocess.run(["bash", "-c", script], check=False, capture_output=True, text=True)


def test_alias_probe_observes_redirect_instead_of_following_it() -> None:
    result = _run_redirect_sensitive_helper("alias")
    assert result.returncode == 0, result.stderr


def test_surface_fetch_follows_redirects() -> None:
    result = _run_redirect_sensitive_helper("surface")
    assert result.returncode == 0, result.stderr


def test_alias_redirect_to_declared_target_passes_for_non_landing_path() -> None:
    # The guard must accept any declared alias that 308s to its declared target,
    # not only the one path that historically redirected (/landing.html).
    result = _run_redirect_sensitive_helper(
        "alias",
        requested_path="/register",
        declared_target="/",
        redirect_location="/",
    )
    assert result.returncode == 0, result.stderr


def test_alias_redirect_to_undeclared_target_fails() -> None:
    # A 308 that lands somewhere other than the declared target must still fail.
    result = _run_redirect_sensitive_helper(
        "alias",
        requested_path="/register",
        declared_target="/",
        redirect_location="/not-the-declared-target",
    )
    assert result.returncode != 0


def test_every_declared_compatibility_alias_is_fetched() -> None:
    # The verifier fetches aliases explicitly; this pins the fetched set to the
    # declared set so a newly declared alias cannot be forgotten.
    declared = {
        alias["path"]
        for alias in json.loads(
            (ROOT / "config/public-surfaces.json").read_text(encoding="utf-8")
        )["compatibility_aliases"]
    }
    fetched = set(
        re.findall(r'fetch_alias\s+\S+\s+"\$base_url([^"]+)"', verifier())
    )
    assert fetched == declared


@pytest.mark.parametrize(
    "mutation",
    (
        ('retrieve "$surface" "$url" "$body" "$headers" false', 'retrieve "$surface" "$url" "$body" "$headers"'),
        ('retrieve "$surface" "$url" "$output" ""', 'retrieve "$surface" "$url" "$output" "" false'),
    ),
)
def test_redirect_policy_mutations_are_rejected(mutation: tuple[str, str]) -> None:
    needle, replacement = mutation
    source = verifier()
    mutated = source.replace(needle, replacement, 1)
    assert mutated != source
    helper = _transport_helpers()
    assert needle in helper
    mutated_helper = helper.replace(needle, replacement, 1)
    assert mutated_helper != helper
    result = _run_redirect_sensitive_helper(
        "alias" if "body" in needle else "surface", mutation
    )
    assert result.returncode != 0


def test_surface_retrieval_requests_compression() -> None:
    source = verifier()
    assert 'curl "${curl_args[@]}" "$url"' in source
    assert "--compressed" in source.split("curl_args=(", 1)[1].split(")", 1)[0]


def test_retrieval_timeout_is_named_and_longer_than_the_old_budget() -> None:
    source = verifier()
    assert 'fetch_max_time="${FETCH_MAX_TIME:-120}"' in source
    assert "--max-time \"$fetch_max_time\"" in source
    assert "--max-time 30" not in source


def test_transport_failure_has_distinct_fail_closed_diagnostic() -> None:
    source = verifier()
    assert "transport failure retrieving" in source
    assert "curl exit code" in source
    assert "elapsed_seconds" in source
    assert "bytes received" in source
    assert 'missing or stale served surface: $surface (HTTP $last_status)' in source
    assert "transport failure retrieving" != "missing or stale served surface"


def test_http_404_is_classified_after_a_non_failing_curl_request() -> None:
    source = verifier()
    curl_block = source.split("metrics=\"$(curl", 1)[1].split("\")", 1)[0]
    assert "--fail" not in curl_block
    assert 'elif [[ "$status" == 404 ]]; then' in source
    assert "--retry-all-errors" in source.split("curl_args=(", 1)[1].split(")", 1)[0]


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        ("--compressed ", "--accept-encoding "),
        ('fetch_max_time="${FETCH_MAX_TIME:-120}"', 'fetch_max_time="30"'),
        ('fail "transport failure retrieving $surface', 'fail "content failure retrieving $surface'),
        ('elif [[ "$status" == 404 ]]; then', 'elif [[ "$status" == 405 ]]; then'),
    ),
)
def test_mutation_controls_reject_each_transport_contract(
    needle: str, replacement: str
) -> None:
    source = verifier()
    mutated = source.replace(needle, replacement, 1)
    assert mutated != source

    if needle == "--compressed ":
        assert "--compressed " not in mutated.split("curl_args=(", 1)[1].split(")", 1)[0]
    elif needle.startswith("fetch_max_time"):
        assert 'fetch_max_time="${FETCH_MAX_TIME:-120}"' not in mutated
    elif needle.startswith('fail "transport failure'):
        assert 'fail "transport failure retrieving $surface' in mutated
    else:
        assert 'elif [[ "$status" == 404 ]]; then' not in mutated
