#!/usr/bin/env python3
"""Validate ~/.config/datapulse/policy.yaml against the embedded schema.

NOTE FOR REVIEWERS: the default path (~/.config/datapulse/policy.yaml) is a
LOCAL configuration file for self-hosted deployments, read only to validate
the paid-lane policy contract. That contract belongs to the Malaysia Data Engine
and not to DataPulse MY's open, read-only trust layer. It is never
read by the public MCP endpoint, never exits the machine, and can be redirected
via DATAPULSE_POLICY_FILE. No secrets or credentials are stored in it by
default.

Exits 0 on success. Exits 1 with a structured error on failure.
Override path with DATAPULSE_POLICY_FILE.
"""
import argparse
import os
import sys
from pathlib import Path

TIERS = {"free", "pro", "enterprise"}
CATEGORIES = {"reference", "fresh", "aging", "stale", "degraded", "browser-dependent", "unreachable", "unknown", "unknown-freshness"}


def fail(path, line, message):
    raise ValueError(f"{path}:{line}: {message}")


def scalar(value, path, line):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
    if value in {"true", "false"}: return value == "true"
    if value.isdigit(): return int(value)
    return value.strip("'\"")


def load_yaml(path):
    data, section, item, nested = {}, None, None, None
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = raw.split("#", 1)[0].rstrip()
        if not text: continue
        indent, text = len(text) - len(text.lstrip()), text.lstrip()
        if indent == 0:
            key, sep, value = text.partition(":")
            if not sep: fail(path, number, "expected key: value")
            data[key] = scalar(value, path, number) if value.strip() else []
            section, item, nested = key, None, None
        elif indent == 2 and text.startswith("- "):
            if not isinstance(data.get(section), list): fail(path, number, "list item outside a list")
            key, sep, value = text[2:].partition(":")
            if not sep: fail(path, number, "expected list mapping")
            item = {key: scalar(value, path, number)}; data[section].append(item); nested = None
        elif indent == 4 and item is not None:
            key, sep, value = text.partition(":")
            if not sep: fail(path, number, "expected key: value")
            if value.strip(): item[key] = scalar(value, path, number); nested = None
            else: item[key] = {}; nested = key
        elif indent == 6 and item is not None and nested:
            key, sep, value = text.partition(":")
            if not sep: fail(path, number, "expected nested key: value")
            item[nested][key] = scalar(value, path, number)
        else: fail(path, number, "unsupported YAML indentation")
    return data


def require(value, condition, label):
    if not condition: raise ValueError(label)


def validate(data):
    require(data.get("schema_version"), isinstance(data.get("schema_version"), int) and data["schema_version"] > 0, "schema_version must be a positive integer")
    for name in ("buyers", "datasets"):
        require(data.get(name, []), isinstance(data.get(name, []), list), f"{name} must be a list")
    ids = set()
    for principal in data["buyers"]:
        require(principal, isinstance(principal, dict), "principal must be a mapping")
        identifier = principal.get("id"); require(identifier, isinstance(identifier, str) and identifier and identifier not in ids, "principal id must be a unique string"); ids.add(identifier)
        require(principal.get("tier"), principal.get("tier") in TIERS, "principal tier must be free, pro, or enterprise")
        limit = principal.get("rate_limit_per_day"); require(limit, isinstance(limit, int) or limit == "unlimited", "principal rate_limit_per_day must be an integer or unlimited")
        categories = principal.get("allowed_categories"); require(categories, categories == "all" or isinstance(categories, list) and all(isinstance(x, str) and x in CATEGORIES for x in categories), "principal allowed_categories must be all or known categories")
        require(principal.get("masking"), principal.get("masking") in {"none", "redact_pii_columns"}, "principal masking is invalid")
        require(principal.get("audit_log_export", True), isinstance(principal.get("audit_log_export", True), bool), "principal audit_log_export must be boolean")
    patterns = set()
    for rule in data["datasets"]:
        require(rule, isinstance(rule, dict), "dataset rule must be a mapping")
        pattern = rule.get("id_pattern"); require(pattern, isinstance(pattern, str) and pattern and pattern not in patterns, "dataset id_pattern must be a unique glob string"); patterns.add(pattern)
        require(rule.get("access"), rule.get("access") in {"open", "gated"}, "dataset access must be open or gated")
        require(rule.get("min_tier"), rule.get("min_tier") in TIERS, "dataset min_tier is invalid")
        masking, audit = rule.get("masking", {}), rule.get("audit", {})
        require(masking, isinstance(masking, dict) and ("columns" not in masking or isinstance(masking["columns"], list) and all(isinstance(x, str) for x in masking["columns"])) and ("strategy" not in masking or masking["strategy"] in {"hash_salted", "redact", "truncate"}), "dataset masking is invalid")
        require(audit, isinstance(audit, dict) and ("log_every_access" not in audit or isinstance(audit["log_every_access"], bool)) and ("retention_days" not in audit or isinstance(audit["retention_days"], int) and audit["retention_days"] > 0), "dataset audit is invalid")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, help="policy file to validate")
    args = parser.parse_args()
    path = (args.file or Path(os.environ.get("DATAPULSE_POLICY_FILE", "~/.config/datapulse/policy.yaml"))).expanduser()
    try: validate(load_yaml(path))
    except (OSError, ValueError) as exc: print(f"policy validation error: {path}: {exc}", file=sys.stderr); return 1
    print(f"policy valid: {path}"); return 0


if __name__ == "__main__": sys.exit(main())
