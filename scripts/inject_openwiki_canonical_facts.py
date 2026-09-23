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

Count claims may use spaces or hyphens (for example ``418 datasets``,
``418-dataset``, ``19 read-only tools``, ``19-read-only-tool``, or ``19 tools``);
the injector rewrites the numeric component while preserving the surrounding
prose form.

It also rejects (case-insensitive) the obsolete apex host
``https://data-pulse.my`` and stale current count claims in any supported
space- or hyphen-separated form, and rejects commercial or retired-boundary
claims (a price, paid tier or quota, payment processor, or an authenticated
API surface this repository does not serve) while allowing honest statements
of absence. The OpenWiki generator occasionally emits content that fails one
or more of these checks.

This post-processor is the deterministic safety net that rewrites the four
allowed pages to satisfy the contract:

1. Strip any previously-injected ``## Canonical facts`` section (idempotent).
2. Replace arbitrary stale current count literals with the current count.
3. Replace the obsolete public product name with the canonical config name.
4. Rewrite the obsolete apex host to the canonical ``www.`` host (using a
   negative lookbehind so a URL that already starts with ``www.`` is
   untouched).
5. Neutralise literal authority claims with safe factual text, then remove the
   whole sentence (or the list item or table row) carrying a commercial or
   retired-boundary claim, leaving negated statements of absence intact.
6. Append a fresh ``## Canonical facts`` section listing the canonical facts
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
from scripts.verify_openwiki import COMMERCIAL_RULES, find_forbidden_claim, is_negated

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
    "- Product: {product_name}\n"
    "- Canonical website: {website}\n"
    "- Datasets: {datasets_count} datasets\n"
    "- MCP server: {tools_count} read-only tools\n"
)

_DATASET_COUNT_RE = re.compile(r"\b\d+(?=[ -]datasets?\b)", re.IGNORECASE)
_READ_ONLY_TOOL_COUNT_RE = re.compile(r"\b\d+(?=[ -]read-only[ -]tools?\b)", re.IGNORECASE)
_TOOL_COUNT_RE = re.compile(r"\b\d+(?=[ -]tools?\b)", re.IGNORECASE)


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


def _rewrite_current_counts(text: str, datasets_count: int, tools_count: int) -> str:
    """Replace count numbers while preserving prose and compound-word forms."""
    text = _DATASET_COUNT_RE.sub(str(datasets_count), text)
    text = _READ_ONLY_TOOL_COUNT_RE.sub(str(tools_count), text)
    return _TOOL_COUNT_RE.sub(str(tools_count), text)


def _rewrite_stale_brand(text: str, product_name: str) -> str:
    """Keep the four current derivatives on the configured public identity."""
    return re.sub(r"\bDataPulse MY\b", product_name, text, flags=re.IGNORECASE)


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
    """Apply the literal claim mapping, leaving honest negatives untouched."""
    for claim, replacement in _NEUTRALIZATIONS:
        pattern = re.compile(re.escape(claim), re.IGNORECASE)

        def _replace(match: re.Match[str], _current: str = text) -> str:
            if is_negated(_current, match.start(), match.end()):
                return match.group(0)
            return replacement

        text = pattern.sub(_replace, text)
    return text


# Removal units for the commercial and retired-boundary class the verifier
# rejects. The withdrawn claims were free prose, so no phrase-level substitute
# can be spliced in without leaving visible wreckage (a negation wedged into
# the middle of a noun phrase). The operator's decision is that the sentence
# carrying the claim goes as a whole. The unit is the smallest
# Markdown-addressable record that still reads cleanly after removal:
#
# * a table row or a list item is one record, so the whole line is dropped; a
#   half-removed cell or a dangling list marker is itself wreckage;
# * prose is dropped sentence-by-sentence within its line, so honest sibling
#   sentences on the same source line survive byte-for-byte. Boundaries are
#   confined to a single line because generated pages write a paragraph as one
#   source line; the verifier wraps prose mid-sentence, and refusing to cross a
#   line break keeps a drop from ever spilling into a neighbouring block.
#
# Negation is decided against the original text with the verifier's own
# is_negated(), so an honest statement of absence ("operates no authenticated
# API", "sells nothing") survives exactly as written.
_SENTENCE_TERMINATOR_RE = re.compile(r"[.!?]+(?=\s|$)")
_TABLE_ROW_RE = re.compile(r"^\s*\|")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _line_bounds(text: str, index: int) -> tuple[int, int]:
    """Return the ``(start, end)`` offsets of the line containing ``index``."""
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return start, (len(text) if end == -1 else end)


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """Return the sentence containing ``[start, end)`` inside its own line.

    A ``.`` followed by a digit (a decimal) is not a boundary; a terminator is
    only a boundary when whitespace or end-of-text follows it.
    """
    line_start, line_end = _line_bounds(text, start)
    last: re.Match[str] | None = None
    for last in _SENTENCE_TERMINATOR_RE.finditer(text[line_start:start]):
        pass
    if last is None:
        sentence_start = line_start
    else:
        sentence_start = line_start + last.end()
        while sentence_start < line_end and text[sentence_start] in " \t":
            sentence_start += 1
    match = _SENTENCE_TERMINATOR_RE.search(text, end)
    if match is None or match.end() > line_end:
        sentence_end = line_end
    else:
        sentence_end = match.end()
        while sentence_end < line_end and text[sentence_end] in " \t":
            sentence_end += 1
    return sentence_start, sentence_end


def _removal_unit(text: str, start: int, end: int) -> tuple[int, int]:
    """Return the unit to drop for a claim matched on ``[start, end)``."""
    line_start, line_end = _line_bounds(text, start)
    end_line_start, end_line_end = _line_bounds(text, end)
    if end_line_start != line_start:
        # A rule matched across a line break; drop the whole spanned block.
        return line_start, end_line_end
    line = text[line_start:line_end]
    if _TABLE_ROW_RE.match(line) or _LIST_ITEM_RE.match(line):
        return line_start, line_end
    return _sentence_bounds(text, start, end)


def _expand_unit_for_removal(text: str, start: int, end: int) -> tuple[int, int]:
    """Drop the line break when the unit is the whole line, so no blank line remains."""
    start_line_start, _ = _line_bounds(text, start)
    _, end_line_end = _line_bounds(text, end)
    if not text[start_line_start:start].strip() and not text[end:end_line_end].strip():
        return start_line_start, min(end_line_end + 1, len(text))
    return start, end


def _commercial_removal_spans(text: str) -> list[tuple[int, int]]:
    """Select non-overlapping units to remove for positive commercial claims.

    Negation is decided against the original text, before any removal, so a
    unit dropped earlier cannot hide or expose a later claim.
    """
    units: list[tuple[int, int]] = []
    for _label, pattern in COMMERCIAL_RULES:
        for match in pattern.finditer(text):
            if is_negated(text, match.start(), match.end()):
                continue
            units.append(_removal_unit(text, match.start(), match.end()))
    units.sort()
    merged: list[tuple[int, int]] = []
    for start, end in units:
        if merged and start <= merged[-1][1]:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return [_expand_unit_for_removal(text, start, end) for start, end in merged]


def _neutralize_commercial_claims(text: str) -> str:
    """Remove the whole sentence (or list item/table row) carrying a claim."""
    for start, end in reversed(_commercial_removal_spans(text)):
        text = text[:start] + text[end:]
    return text


def _canonical_section(product_name: str, website: str, datasets_count: int, tools_count: int) -> str:
    body = _SECTION_TEMPLATE.format(
        product_name=product_name,
        website=website,
        datasets_count=datasets_count,
        tools_count=tools_count,
    )
    # Reject accidental introduction of any claim the verifier rejects, using
    # the verifier's own matcher so the two stay in lockstep.
    claim = find_forbidden_claim(body)
    if claim is not None:
        label, matched = claim
        raise InjectError(
            f"canonical section would contain forbidden claim ({label}): {matched!r}"
        )
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
    try:
        product_name = load_public_surfaces(root)["product_name"]
    except GenerationError as error:
        raise InjectError(f"cannot read canonical product name from public-surfaces: {error}") from error
    if "www.data-pulse.my" not in website:
        raise InjectError(
            f"canonical website {website!r} does not include the www. subdomain; refusing to inject"
        )
    datasets_count = _load_count(root, "datapulse.json", "datasets")
    tools_count = _load_count(root, "mcp.json", "tools")
    section = _canonical_section(product_name, website, datasets_count, tools_count)

    results: list[tuple[str, str]] = []
    for relative in PAGES:
        path = root / relative
        if not path.is_file():
            raise InjectError(f"missing required page: {relative}")
        original = path.read_text(encoding="utf-8")
        rewritten = _strip_existing_block(original)
        rewritten = _rewrite_stale_brand(rewritten, product_name)
        rewritten = _rewrite_current_counts(rewritten, datasets_count, tools_count)
        rewritten = _rewrite_obsolete_url(rewritten)
        rewritten = _neutralize_forbidden_claims(rewritten)
        rewritten = _neutralize_commercial_claims(rewritten)
        # Fail closed: never write a page we could not rewrite cleanly. If a
        # positive claim survived removal, refuse the whole injection rather
        # than publish a page the verifier will reject.
        claim = find_forbidden_claim(rewritten)
        if claim is not None:
            label, matched = claim
            raise InjectError(
                f"{relative} still contains a forbidden claim ({label}) after rewrite: {matched!r}"
            )
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
