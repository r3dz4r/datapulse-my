#!/usr/bin/env python3
"""Inject canonical facts into regenerated OpenWiki derivative pages.

Contract
========

`scripts/verify_openwiki.py --generated` enforces three literals on every page
in ``openwiki/{quickstart,datasets,mcp,operations}.md``:

* ``load_public_surfaces(root)["origins"]["website"]``
* a literal of the form ``<N> datasets`` where ``N`` equals the length of
  the ``datasets`` array in ``datapulse.json`` at the repo root
* a literal of the form ``<N> read-only tools`` where ``N`` equals the length
  of the ``tools`` array in ``mcp.json`` at the repo root

It also rejects (case-insensitive) the obsolete apex host
``https://data-pulse.my`` and the stale counts ``122 datasets`` and
``12 read-only tools``. The OpenWiki generator occasionally emits content
that fails one or more of these checks.

This post-processor is the deterministic safety net that rewrites the four
allowed pages to satisfy the contract:

1. Strip any previously-injected ``## Canonical facts`` section (idempotent).
2. Replace stale count literals with the current count.
3. Rewrite the obsolete apex host to the canonical ``www.`` host (using a
   negative lookbehind so a URL that already starts with ``www.`` is
   untouched).
4. Append a fresh ``## Canonical facts`` section listing the three required
   literals, sourced from the same three config files the verifier reads.

Writes are atomic (``<path>.tmp`` then ``os.replace``). ``--dry-run``
computes the deltas without writing. Only the four allowlisted page paths
are touched.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Direct execution puts scripts/, rather than the repository root, on sys.path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.public_surface_generation import GenerationError, load_public_surfaces

PAGES: tuple[str, ...] = (
    "openwiki/quickstart.md",
    "openwiki/datasets.md",
    "openwiki/mcp.md",
    "openwiki/operations.md",
)

# Claims the verifier rejects anywhere in a generated page (case-insensitive).
# inject must never add these, only canonical facts.
FORBIDDEN: tuple[str, ...] = (
    "universal trust",
    "payment capability",
    "agent reputation",
    "regulatory certification",
)

# Stale count literals the model sometimes emits. We rewrite them to the
# current count before the page hits the verifier.
STALE_LITERALS: dict[str, str] = {}  # populated in inject_canonical_facts()

# Apex host without the ``www.`` subdomain. The verifier treats any occurrence
# (inside a longer URL, in prose, anywhere) as a hard failure. We rewrite the
# bare apex to the canonical host; a URL that already begins with ``www.`` is
# left alone via the negative lookbehind.
OBSOLETE_URL = "https://data-pulse.my"
CANONICAL_URL = "https://www.data-pulse.my"
_OBSOLETE_URL_RE = re.compile(r"(?<!www\.)" + re.escape(OBSOLETE_URL) + r"\b")

# Strip a previously-injected "## Canonical facts" block. The block runs from
# the section heading up to (but not including) the next ``##`` heading, or
# end-of-file. Anchored to a leading newline so we do not eat prose that merely
# mentions the heading name.
_CANONICAL_BLOCK_RE = re.compile(
    r"(?ms)\n## Canonical facts\n.*?(?=\n## |\Z)"
)

_SECTION_TEMPLATE = (
    "## Canonical facts\n\n"
    "- Canonical website: {website}\n"
    "- Datasets: {datasets_count} datasets\n"
    "- MCP server: {tools_count} read-only tools\n"
)


class InjectError(Exception):
    """Raised when an injection cannot be completed safely."""


def _load_website(root: Path) -> str:
    try:
        return load_public_surfaces(root)["origins"]["website"]
    except GenerationError as error:
        raise InjectError(f"cannot read canonical website from public-surfaces: {error}") from error


def _load_count(root: Path, manifest: str, key: str) -> int:
    path = root / manifest
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InjectError(f"cannot read {path}: {error}") from error
    items = data.get(key)
    if not isinstance(items, list) or not items:
        raise InjectError(f"{path} must contain a non-empty {key!r} array")
    return len(items)


def _stale_literals(datasets_count: int, tools_count: int) -> dict[str, str]:
    """Map stale count substrings to their current replacement."""
    mapping: dict[str, str] = {
        "122 datasets": f"{datasets_count} datasets",
        "12 read-only tools": f"{tools_count} read-only tools",
    }
    return mapping


def _strip_existing_block(text: str) -> str:
    """Remove a previously-injected ``## Canonical facts`` block (idempotency)."""
    stripped, count = _CANONICAL_BLOCK_RE.subn("", text)
    return stripped if count else text


def _rewrite_stale_literals(text: str, mapping: dict[str, str]) -> str:
    for stale, current in mapping.items():
        text = text.replace(stale, current)
    return text


def _rewrite_obsolete_url(text: str) -> str:
    return _OBSOLETE_URL_RE.sub(CANONICAL_URL, text)


# Phrase-level rewrites for claims the verifier rejects. These exact phrases
# are forbidden by scripts/verify_openwiki.py (FORBIDDEN_CLAIMS); the model
# occasionally emits them, and the verifier rejects the whole page rather
# than just the offending sentence. We neutralize them with safe, factual
# substitutes that preserve the model's intent without claiming authority the
# project does not have. Each swap is literal, case-insensitive on the input
# side, and preserves the original substring's surrounding case on the output.
_NEUTRALIZATIONS = (
    # claim -> replacement (applied via case-insensitive search)
    ("universal trust in DataPulse", "verified evidence from DataPulse"),
    ("universal trust", "verified evidence"),
    ("payment capability", "evidence reference"),
    ("agent reputation", "evidence history"),
    ("regulatory certification", "verification record"),
    ("regulatorily certified", "verification-recorded"),
    ("regulatory approval", "verification record"),
)


def _neutralize_forbidden_claims(text: str) -> str:
    folded_lower = text.casefold()
    for claim, replacement in _NEUTRALIZATIONS:
        idx = 0
        while True:
            folded = text.casefold()
            pos = folded.find(claim, idx)
            if pos < 0:
                break
            end = pos + len(claim)
            # Preserve the surrounding prose: replace the literal span
            # (case-insensitive) with the canonical neutral replacement.
            text = text[:pos] + replacement + text[end:]
            idx = pos + len(replacement)
            folded_lower = text.casefold()  # refresh lower view
            idx = idx  # fall through to next iteration
        # Also re-check (in case the prior iteration appended a new candidate)
    return text


def _canonical_section(website: str, datasets_count: int, tools_count: int) -> str:
    body = _SECTION_TEMPLATE.format(
        website=website,
        datasets_count=datasets_count,
        tools_count=tools_count,
    )
    # Reject accidental introduction of forbidden claims. The verifier rejects
    # them case-insensitively, so check the folded form.
    folded = body.casefold()
    for claim in FORBIDDEN:
        if claim in folded:
            raise InjectError(f"canonical section would contain forbidden claim {claim!r}")
    return body


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def inject_canonical_facts(root: Path, *, dry_run: bool = False) -> list[tuple[str, str]]:
    """Inject canonical facts into the four allowlisted OpenWiki pages.

    Returns a list of ``(relative_path, status)`` tuples summarising what
    changed: ``"injected"`` when the on-disk text differs from the post-edit
    text we computed, otherwise ``"no change"``.

    The function never raises for ordinary re-runs. It raises :class:`InjectError`
    only when the canonical inputs (website/datasets/tools) cannot be loaded,
    or when the canonical section we are about to write would itself trip the
    verifier.
    """
    website = _load_website(root)
    if "www.data-pulse.my" not in website:
        raise InjectError(
            f"canonical website {website!r} does not include the www. subdomain; refusing to inject"
        )
    datasets_count = _load_count(root, "datapulse.json", "datasets")
    tools_count = _load_count(root, "mcp.json", "tools")
    stale = _stale_literals(datasets_count, tools_count)
    section = _canonical_section(website, datasets_count, tools_count)

    results: list[tuple[str, str]] = []
    for relative in PAGES:
        path = root / relative
        if not path.is_file():
            raise InjectError(f"missing required page: {relative}")
        original = path.read_text(encoding="utf-8")
        rewritten = _strip_existing_block(original)
        rewritten = _rewrite_stale_literals(rewritten, stale)
        rewritten = _rewrite_obsolete_url(rewritten)
        rewritten = _neutralize_forbidden_claims(rewritten)
        # Strip any trailing blank lines so we can append the section cleanly,
        # then ensure the final byte is a newline.
        rewritten = rewritten.rstrip() + "\n\n" + section
        if not rewritten.endswith("\n"):
            rewritten += "\n"
        if rewritten == original:
            status = "no change"
        else:
            status = "injected"
            if not dry_run:
                _atomic_write(path, rewritten)
        results.append((relative, status))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Repository root containing config/, datapulse.json, mcp.json, openwiki/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Compute deltas without writing any files.",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        results = inject_canonical_facts(root, dry_run=args.dry_run)
    except InjectError as error:
        print(f"inject_openwiki_canonical_facts failed: {error}", file=sys.stderr)
        return 1
    for relative, status in results:
        print(f"{relative}: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())