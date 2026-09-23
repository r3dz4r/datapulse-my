#!/usr/bin/env python3
"""Fail closed when derivative OpenWiki documentation escapes its contract."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Direct execution puts scripts/, rather than the repository root, on sys.path.
    sys.path.insert(0, str(ROOT))

from scripts.public_surface_generation import GenerationError, load_public_surfaces


GENERATED_PATHS = frozenset(
    {
        "openwiki/quickstart.md",
        "openwiki/datasets.md",
        "openwiki/mcp.md",
        "openwiki/operations.md",
        "openwiki/.last-update.json",
    }
)
MANAGED_INSTRUCTION_PATHS = frozenset({"AGENTS.md", "CLAUDE.md"})
REQUIRED_PAGES = GENERATED_PATHS - {"openwiki/.last-update.json"}
FORBIDDEN_CLAIMS = (
    "universal trust",
    "payment capability",
    "agent reputation",
    "regulatory certification",
)
_DATASET_COUNT_RE = re.compile(r"\b(?P<count>\d+)(?=[ -]datasets?\b)", re.IGNORECASE)
_READ_ONLY_TOOL_COUNT_RE = re.compile(r"\b(?P<count>\d+)(?=[ -]read-only[ -]tools?\b)", re.IGNORECASE)
_TOOL_COUNT_RE = re.compile(r"\b(?P<count>\d+)(?=[ -]tools?\b)", re.IGNORECASE)

# A page can publish a price, quota, paid tier or a retired API boundary
# without naming any of the four literal phrases above, because the withdrawn
# claim was free prose. These patterns describe that class of paraphrase; the
# negation guard below then exempts honest statements of absence such as
# "this repository operates no authenticated API" (or the prohibition sentence
# in openwiki/INSTRUCTIONS.md). Bare "tier"/"rate" are deliberately absent:
# the health pipeline has a non-commercial `--tier` filter and anomaly rates.
_CURRENCY = (
    r"(?:USD|MYR|SGD|EUR|GBP|AUD|CAD|JPY|CNY|IDR|THB|PHP|INR|"
    r"RM|US\$|S\$|A\$|HK\$|\$|€|£|¥)"
)
_PERIOD = r"(?:month|year|annum|quarter|week|day|seat|user|call|request|token|credit)"
_PRICE = r"(?:price|pricing|fee|fees|cost|costs|rate|rates|charge|charges|subscription|billing)"
_CURRENCY_AMOUNT = (
    rf"(?:(?<![A-Za-z]){_CURRENCY}\s?\d[\d,]*(?:\.\d{{1,2}})?"
    rf"|\d[\d,]*(?:\.\d{{1,2}})?\s?(?:{_CURRENCY}|dollars?|ringgit|cents?)\b)"
)
COMMERCIAL_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "named payment processor",
        re.compile(
            r"\b(?:Paddle|Stripe|PayPal|Braintree|Chargebee|Recurly|"
            r"Lemon\s?Squeezy|Gumroad|Razorpay|Billplz|SenangPay|iPay88|"
            r"2C2P|Adyen|Worldpay|Klarna|Afterpay|Checkout\.com|"
            r"FastSpring|Payhip)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "commercial price",
        re.compile(
            rf"{_CURRENCY_AMOUNT}(?:\s*(?:/|per\s+|a\s+)(?:{_PERIOD})\b)?",
            re.IGNORECASE,
        ),
    ),
    (
        "per-period price",
        re.compile(
            rf"\b{_PRICE}\b[^\n.;|]{{0,40}}?\bper\b"
            rf"|\b(?:monthly|annual|annually|yearly|quarterly|weekly|daily)\b"
            rf"[^\n.;|]{{0,30}}?\b{_PRICE}\b"
            rf"|\b{_PRICE}\b[^\n.;|]{{0,30}}?\b"
            rf"(?:monthly|annual|annually|yearly|quarterly|weekly|daily)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "paid tier, plan, or quota",
        re.compile(
            r"\b(?:paid|premium|pro|enterprise|pricing|subscription|billing|"
            r"commercial|monthly|annual|yearly|free)\s+"
            r"(?:tier|tiers|plan|plans|package|packages|edition|editions|"
            r"seat|seats|account|accounts|offering|offerings)\b"
            r"|\b(?:quota|quotas|subscription|subscriptions|entitlement|"
            r"entitlements|paid|premium)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "paid product or authenticated API",
        re.compile(
            r"\b(?:paid|commercial|chargeable|billable)\s+"
            r"(?:product|products|service|services|offering|offerings|"
            r"edition|editions|terms|licence|license|offer)\b"
            r"|\bbuyer\s+(?:api|boundary|endpoint|surface)\b"
            r"|(?<![A-Za-z0-9])/api/v\d+/?(?![A-Za-z0-9])"
            r"|\bauthenticated\s+(?:buyer\s+)?(?:api|endpoint|surface|route|"
            r"service|interface)\b"
            r"|\b(?:api|access)\s+(?:key|token)s?\b"
            r"|\bauthentication\s+(?:is\s+)?required\b",
            re.IGNORECASE,
        ),
    ),
)

# Negation-aware guard. A claim is legitimate when it is stated as absent:
# "operates no authenticated API", "does not sell a paid product", or the
# instruction "never state a price, tier, paid quota". We look back within the
# current clause, stop at a contrastive conjunction so "no free tier, but a
# monthly fee" still fires, and also catch a directly negated predicate.
_CLAUSE_BOUNDARY_RE = re.compile(r"[.;:!?|\u2014\u2013]|\n{2,}")
_SUFFIX_BOUNDARY_RE = re.compile(r"[.;:!?|\n\u2014\u2013]")
_CONTRAST_RE = re.compile(
    r"\b(?:but|however|yet|although|though|whereas|nevertheless|nonetheless|"
    r"except|instead)\b",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(
    r"(?:\b(?:no|not|never|none|neither|nor|without|cannot|can't|won't|"
    r"doesn't|don't|isn't|aren't|wasn't|weren't|hasn't|haven't|didn't|"
    r"nothing|zero)\b|n't\b)",
    re.IGNORECASE,
)
_SUFFIX_NEGATION_RE = re.compile(r"\b(?:not|never|no longer)\b", re.IGNORECASE)


class VerificationError(Exception):
    """Raised when a generated documentation contract is violated."""


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{path} must contain a JSON object")
    return value


def _facts(root: Path) -> tuple[str, str, int, int]:
    try:
        public = load_public_surfaces(root)
        website = public["origins"]["website"]
        product_name = public["product_name"]
    except GenerationError as error:
        raise VerificationError(str(error)) from error
    manifest = _load_object(root / "datapulse.json")
    mcp = _load_object(root / "mcp.json")
    datasets = manifest.get("datasets")
    tools = mcp.get("tools")
    if not isinstance(datasets, list) or not datasets:
        raise VerificationError("datapulse.json must contain a non-empty datasets array")
    if not isinstance(tools, list) or not tools:
        raise VerificationError("mcp.json must contain a non-empty tools array")
    return product_name, website, len(datasets), len(tools)


def _has_stale_count(text: str, current: int, pattern: re.Pattern[str]) -> bool:
    return any(int(match.group("count")) != current for match in pattern.finditer(text))


def _clause_prefix(text: str, start: int) -> str:
    """Return the current clause text preceding ``start``.

    A single newline is not a boundary: generated pages and
    openwiki/INSTRUCTIONS.md wrap prose mid-sentence, so the negation in
    "never state a price ... or a commercial offer" must survive the wrap.
    """
    prefix = text[:start]
    boundaries = list(_CLAUSE_BOUNDARY_RE.finditer(prefix))
    if boundaries:
        prefix = prefix[boundaries[-1].end() :]
    prefix = prefix[-240:]
    contrasts = list(_CONTRAST_RE.finditer(prefix))
    if contrasts:
        prefix = prefix[contrasts[-1].end() :]
    return prefix


def is_negated(text: str, start: int, end: int) -> bool:
    """True when a claim span sits inside a statement of absence.

    Shared with the injector so neutralisation and rejection agree on what
    counts as an honest negative ("operates no authenticated API").
    """
    if _NEGATION_RE.search(_clause_prefix(text, start)):
        return True
    suffix = text[end:]
    boundary = _SUFFIX_BOUNDARY_RE.search(suffix)
    if boundary:
        suffix = suffix[: boundary.start()]
    return bool(_SUFFIX_NEGATION_RE.search(suffix[:120]))


def _literal_claim(text: str, claim: str) -> tuple[int, int] | None:
    folded = text.casefold()
    position = 0
    while True:
        index = folded.find(claim, position)
        if index < 0:
            return None
        if not is_negated(text, index, index + len(claim)):
            return index, index + len(claim)
        position = index + 1


def find_forbidden_claim(text: str) -> tuple[str, str] | None:
    """Return the (label, matched text) of the first positive forbidden claim."""
    for claim in FORBIDDEN_CLAIMS:
        span = _literal_claim(text, claim)
        if span is not None:
            return claim, text[span[0] : span[1]]
    for label, pattern in COMMERCIAL_RULES:
        for match in pattern.finditer(text):
            if not is_negated(text, match.start(), match.end()):
                return label, match.group(0)
    return None


def _changed_paths(root: Path, base: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base], cwd=root, capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise VerificationError(f"cannot read generated path diff from {base}: {result.stderr.strip()}")
    return {line for line in result.stdout.splitlines() if line}


def _managed_instruction_change(root: Path, base: str, relative: str) -> bool:
    """Allow only an explicit OpenWiki marker/pointer block in instruction files."""
    original = subprocess.run(["git", "show", f"{base}:{relative}"], cwd=root, capture_output=True, text=True, check=False)
    if original.returncode:
        return False
    try:
        updated = (root / relative).read_text(encoding="utf-8")
    except OSError:
        return False
    marker = re.compile(r"(?ims)^<!-- BEGIN OPENWIKI(?: [A-Z0-9_-]+)? -->.*?^<!-- END OPENWIKI(?: [A-Z0-9_-]+)? -->\n?")
    pointer = re.compile(r"(?im)^<!-- OPENWIKI(?: [A-Z0-9_-]+)? -->\n?")
    return pointer.sub("", marker.sub("", original.stdout)) == pointer.sub("", marker.sub("", updated))


def verify(root: Path, *, generated: bool, changed_from: str | None = None) -> None:
    """Verify canonical facts and the derivative-output ownership boundary."""
    product_name, website, datasets, tools = _facts(root)
    instructions = root / "openwiki/INSTRUCTIONS.md"
    if not instructions.is_file() or website not in instructions.read_text(encoding="utf-8"):
        raise VerificationError("openwiki/INSTRUCTIONS.md must name the canonical website origin")
    if changed_from is not None:
        changed = _changed_paths(root, changed_from)
        forbidden = changed - GENERATED_PATHS - MANAGED_INSTRUCTION_PATHS
        if forbidden:
            raise VerificationError("OpenWiki changed disallowed path(s): " + ", ".join(sorted(forbidden)))
        unmanaged = [path for path in changed & MANAGED_INSTRUCTION_PATHS if not _managed_instruction_change(root, changed_from, path)]
        if unmanaged:
            raise VerificationError("OpenWiki changed non-managed instruction content: " + ", ".join(sorted(unmanaged)))
    if not generated:
        return
    missing = [path for path in sorted(REQUIRED_PAGES) if not (root / path).is_file()]
    if missing:
        raise VerificationError("missing generated OpenWiki page(s): " + ", ".join(missing))
    required_facts = (product_name, website, f"{datasets} datasets", f"{tools} read-only tools")
    for relative in sorted(REQUIRED_PAGES):
        text = (root / relative).read_text(encoding="utf-8")
        folded = text.casefold()
        if "datapulse my" in folded:
            raise VerificationError(f"{relative} uses the obsolete public product name")
        if "https://data-pulse.my" in text:
            raise VerificationError(f"{relative} uses the obsolete apex website origin")
        claim = find_forbidden_claim(text)
        if claim is not None:
            label, matched = claim
            raise VerificationError(
                f"{relative} contains an unsupported claim ({label}): {matched!r}"
            )
        if _has_stale_count(text, datasets, _DATASET_COUNT_RE):
            raise VerificationError(f"{relative} contains stale dataset count facts")
        stale_tool_count = _has_stale_count(text, tools, _READ_ONLY_TOOL_COUNT_RE) or _has_stale_count(
            text, tools, _TOOL_COUNT_RE
        )
        if stale_tool_count:
            raise VerificationError(f"{relative} contains stale MCP tool count facts")
        if not all(fact in text for fact in required_facts):
            raise VerificationError(f"{relative} is missing canonical current facts")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated", action="store_true", help="Validate rendered pages as well as source ownership.")
    parser.add_argument("--changed-from", help="Git revision used to check the generated output allowlist.")
    args = parser.parse_args()
    try:
        verify(ROOT, generated=args.generated, changed_from=args.changed_from)
    except VerificationError as error:
        print(f"OpenWiki verification failed: {error}", file=sys.stderr)
        return 1
    print("OpenWiki verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
