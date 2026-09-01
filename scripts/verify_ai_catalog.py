#!/usr/bin/env python3
"""Verify the checked-in AI resource directory catalog and tool cards."""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from gen_ai_catalog import DEFAULT_CONTACT_EMAIL, PERSONAL_EMAIL, PUBLIC_ORIGIN, build_outputs


ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class OperatorError(Exception):
    """Inputs necessary to verify the catalog are absent or unreadable."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OperatorError(f"missing input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a JSON object")
    return value


def _card_path(root: Path, url: object) -> Path:
    if not isinstance(url, str):
        raise ValueError("catalog entry URL must be a string")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "www.data-pulse.my" or parsed.query or parsed.fragment:
        raise ValueError(f"catalog URL is not a canonical public card URL: {url}")
    match = re.fullmatch(r"/mcp/cards/([a-z][a-z0-9_]*)\.json", parsed.path)
    if match is None:
        raise ValueError(f"catalog URL is outside the card surface: {url}")
    path = (root / "docs" / parsed.path.lstrip("/")).resolve()
    cards_root = (root / "docs/mcp/cards").resolve()
    if path.parent != cards_root:
        raise ValueError(f"catalog URL escapes the card surface: {url}")
    return path


def verify(root: Path, contact_email: str = DEFAULT_CONTACT_EMAIL) -> list[str]:
    """Return every contract defect without mutating the generated public surface."""
    root = root.resolve()
    catalog_path = root / "docs/ai-catalog.json"
    catalog = _read_json(catalog_path)
    errors: list[str] = []
    if catalog.get("specVersion") != "1.0":
        errors.append("catalog specVersion must equal 1.0")
    if catalog.get("ard_spec_version") != "0.9":
        errors.append("catalog ard_spec_version must equal 0.9")
    contract_version = catalog.get("contract_version")
    if not isinstance(contract_version, str) or SEMVER.fullmatch(contract_version) is None:
        errors.append("catalog contract_version must be semver-shaped")
    host = catalog.get("host")
    if not isinstance(host, dict) or "identifier" in host:
        errors.append("catalog host must not contain an identifier")
    publisher = catalog.get("publisher")
    if not isinstance(publisher, dict) or publisher.get("contact_email") == PERSONAL_EMAIL:
        errors.append("catalog publisher.contact_email must be a project contact email")
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        errors.append("catalog entries must be an array")
        entries = []
    try:
        mcp = _read_json(root / "mcp.json")
        tools = mcp.get("tools")
        if not isinstance(tools, list):
            raise OperatorError("mcp.json tools is missing")
        if len(entries) != len(tools):
            errors.append(f"catalog has {len(entries)} entries but mcp.json has {len(tools)} tools")
    except OperatorError:
        raise
    identifiers: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("catalog entries must be objects")
            continue
        identifier = entry.get("identifier")
        if not isinstance(identifier, str):
            errors.append("catalog entry identifier must be a string")
            continue
        if identifier in identifiers:
            errors.append(f"duplicate catalog entry identifier: {identifier}")
        identifiers.add(identifier)
        capabilities = entry.get("capabilities")
        if not isinstance(capabilities, list) or capabilities != sorted(capabilities):
            errors.append(f"catalog entry {identifier} capabilities are not sorted")
        try:
            path = _card_path(root, entry.get("url"))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"missing card file: {path.relative_to(root)}")
            continue
        try:
            card = _read_json(path)
        except (OperatorError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if card.get("identifier") != identifier:
            errors.append(f"card identifier does not match catalog: {path.relative_to(root)}")
        if card.get("contract_version") != contract_version:
            errors.append(f"card contract_version does not match catalog: {path.relative_to(root)}")
    try:
        expected_catalog, expected_cards = build_outputs(root, contact_email)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise OperatorError(f"cannot build expected catalog: {exc}") from exc
    if catalog_path.read_bytes() != expected_catalog:
        errors.append("catalog bytes differ from deterministic generator output")
    for name, expected in expected_cards.items():
        path = root / "docs/mcp/cards" / f"{name}.json"
        if not path.is_file():
            continue
        if path.read_bytes() != expected:
            errors.append(f"card bytes differ from deterministic generator output: {path.relative_to(root)}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--contact-email", default=DEFAULT_CONTACT_EMAIL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        errors = verify(args.root, args.contact_email)
    except OperatorError as exc:
        LOGGER.error("AI catalog verifier operator error: %s", exc)
        return 2
    except (OSError, UnicodeError, ValueError) as exc:
        LOGGER.error("AI catalog verifier failed: %s", exc)
        return 1
    if errors:
        for error in errors:
            LOGGER.error("AI catalog defect: %s", error)
        return 1
    LOGGER.info("AI catalog contract verified for %s", PUBLIC_ORIGIN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
