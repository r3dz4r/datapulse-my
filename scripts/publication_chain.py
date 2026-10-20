#!/usr/bin/env python3
"""Read a JSON publication snapshot on stdin; emit one fail-closed decision."""
from __future__ import annotations

import json
import re
import sys
from typing import TypedDict


class Decision(TypedDict):
    decision: str
    reason: str
    next_depth: int | None


def _stop(reason: str) -> Decision:
    return {"decision": "stop", "reason": reason, "next_depth": None}


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def _depth(value: object) -> int | None:
    if type(value) is int:
        return value if value >= 0 else None
    if isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def decide(inputs: object) -> Decision:
    """Advance only a successful, identified publication within its depth budget."""
    try:
        if not isinstance(inputs, dict):
            return _stop("invalid_input")
        result = inputs.get("publication_result")
        if result not in ("success", "failure", "cancelled", "skipped"):
            return _stop("invalid_publication_result")
        if result != "success":
            return _stop("not_succeeded")
        for field in ("published_sha", "main_sha"):
            if not _valid_sha(inputs.get(field)):
                return _stop(f"invalid_{field}")
        depth = _depth(inputs.get("chain_depth"))
        if depth is None:
            return _stop("invalid_chain_depth")
        maximum = _depth(inputs.get("max_depth"))
        if maximum is None:
            return _stop("invalid_max_depth")
        if inputs["published_sha"] == inputs["main_sha"]:
            return _stop("equal_shas")
        if depth >= maximum:
            return _stop("depth_exhausted")
        return {"decision": "chain", "reason": "newer_main", "next_depth": depth + 1}
    except Exception:
        # An unexpected reader/validation error must never authorize a dispatch.
        return _stop("decision_error")


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields: dict[str, object] = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError("duplicate input field")
        fields[key] = value
    return fields


def _reject_constant(value: str) -> None:
    raise ValueError("non-JSON constant")


def main() -> int:
    """Errors are stop decisions, with the same zero exit status as chaining."""
    try:
        inputs = json.load(
            sys.stdin, object_pairs_hook=_unique_fields, parse_constant=_reject_constant,
        )
    except Exception:
        decision = _stop("unreadable_input")
    else:
        decision = decide(inputs)
    sys.stdout.write(json.dumps(decision, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
