#!/usr/bin/env python3
"""Measure verification-tool latency without changing trust results or artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import perf_counter
from typing import Any, TypeVar


MCP_DIR = Path(__file__).resolve().parent
REPO_DIR = MCP_DIR.parent
for path in (REPO_DIR, MCP_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import server  # noqa: E402


T = TypeVar("T")


def _percentiles(values: list[float]) -> dict[str, float | int]:
    """Return nearest-rank latency percentiles in milliseconds."""
    if not values:
        return {"samples": 0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}
    ordered = sorted(values)

    def percentile(percent: float) -> float:
        return ordered[min(len(ordered) - 1, max(0, int((len(ordered) * percent + 0.999999)) - 1))]

    return {
        "samples": len(ordered),
        "p50_ms": round(percentile(0.50), 3),
        "p95_ms": round(percentile(0.95), 3),
        "p99_ms": round(percentile(0.99), 3),
        "max_ms": round(ordered[-1], 3),
    }


async def _timed(label: str, operation: Callable[[], Awaitable[T]], components: dict[str, list[float]]) -> T:
    started = perf_counter()
    try:
        return await operation()
    finally:
        components[label].append((perf_counter() - started) * 1000)


async def _measure_call(
    label: str, operation: Callable[[], Awaitable[dict[str, Any]]], components: dict[str, list[float]]
) -> dict[str, Any]:
    started = perf_counter()
    try:
        result = await operation()
    except Exception as exc:  # Benchmark output must preserve a fail-closed tool error.
        result = {"benchmark_error": exc.__class__.__name__}
    elapsed = (perf_counter() - started) * 1000
    components[f"tool:{label}"].append(elapsed)
    return result


async def run_benchmark(
    dataset_id: str, samples: int, replay_chain: bool, scenarios_to_run: set[str] | None = None
) -> dict[str, Any]:
    """Run controlled cold/warm samples against the configured published endpoint."""
    components: dict[str, list[float]] = defaultdict(list)
    original_fetch_json = server._fetch_json
    original_fetch_bytes = server._fetch_bytes
    original_live = server._fetch_live_receipts
    original_cosign = server._verify_sigstore_receipt
    original_anchor = server._verify_git_anchor

    async def fetch_json(path: str) -> dict[str, Any]:
        return await _timed("http:published_json", lambda: original_fetch_json(path), components)

    async def fetch_bytes(path: str) -> bytes:
        return await _timed("http:published_bundle", lambda: original_fetch_bytes(path), components)

    async def fetch_live(url: str) -> dict[str, Any]:
        return await _timed("http:live_source", lambda: original_live(url), components)

    def cosign(**kwargs: Any) -> tuple[bool, str]:
        started = perf_counter()
        try:
            return original_cosign(**kwargs)
        finally:
            components["subprocess:cosign"].append((perf_counter() - started) * 1000)

    async def anchor(anchor_data: dict[str, Any], expected_head: str) -> bool:
        return await _timed("http:git_anchor", lambda: original_anchor(anchor_data, expected_head), components)

    server._fetch_json = fetch_json
    server._fetch_bytes = fetch_bytes
    server._fetch_live_receipts = fetch_live
    server._verify_sigstore_receipt = cosign
    server._verify_git_anchor = anchor
    scenarios: dict[str, list[dict[str, Any]]] = defaultdict(list)
    def enabled(name: str) -> bool:
        return scenarios_to_run is None or name in scenarios_to_run

    try:
        for _ in range(samples):
            server._VERIFY_CACHE.clear()
            server._VERIFY_IN_FLIGHT.clear()
            if enabled("verify_dataset_cold"):
                scenarios["verify_dataset_cold"].append(
                    await _measure_call("verify_dataset_cold", lambda: server.verify_dataset(dataset_id), components)
                )
            elif enabled("verify_dataset_warm"):
                await server.verify_dataset(dataset_id)
            if enabled("verify_dataset_warm"):
                scenarios["verify_dataset_warm"].append(
                    await _measure_call("verify_dataset_warm", lambda: server.verify_dataset(dataset_id), components)
                )

            server._VERIFY_CACHE.clear()
            server._VERIFY_IN_FLIGHT.clear()
            if enabled("verify_evidence_live_miss"):
                scenarios["verify_evidence_live_miss"].append(
                    await _measure_call("verify_evidence_live_miss", lambda: server.verify_evidence(dataset_id), components)
                )
            elif enabled("verify_evidence_cache_hit"):
                await server.verify_evidence(dataset_id)
            if enabled("verify_evidence_cache_hit"):
                scenarios["verify_evidence_cache_hit"].append(
                    await _measure_call("verify_evidence_cache_hit", lambda: server.verify_evidence(dataset_id), components)
                )
            if enabled("verify_attestation_l1"):
                scenarios["verify_attestation_l1"].append(
                    await _measure_call("verify_attestation_l1", lambda: server.verify_attestation(dataset_id, False), components)
                )
            if replay_chain and enabled("verify_attestation_l2_replay"):
                scenarios["verify_attestation_l2_replay"].append(
                    await _measure_call("verify_attestation_l2_replay", lambda: server.verify_attestation(dataset_id, True), components)
                )
    finally:
        server._fetch_json = original_fetch_json
        server._fetch_bytes = original_fetch_bytes
        server._fetch_live_receipts = original_live
        server._verify_sigstore_receipt = original_cosign
        server._verify_git_anchor = original_anchor

    timing = {name.removeprefix("tool:"): _percentiles(values) for name, values in components.items() if name.startswith("tool:")}
    return {
        "dataset_id": dataset_id,
        "samples_per_scenario": samples,
        "timing": timing,
        "components": {name: _percentiles(values) for name, values in components.items() if not name.startswith("tool:")},
        "outcomes": {
            name: {
                "successes": sum("benchmark_error" not in result for result in results),
                "signed": sum(result.get("signed") is True for result in results),
                "cached": sum(result.get("cached") is True for result in results),
                "l1_satisfied": sum(result.get("levels", {}).get("L1", {}).get("satisfied") is True for result in results),
                "l2_satisfied": sum(result.get("levels", {}).get("L2", {}).get("satisfied") is True for result in results),
                "errors": sorted({str(result["benchmark_error"]) for result in results if "benchmark_error" in result}),
            }
            for name, results in scenarios.items()
        },
        "notes": [
            "Cold clears only the live-verification cache; CDN and operating-system connection caches may still be warm.",
            "Component timings are inclusive and can overlap because published artifact fetches run concurrently.",
            "A timeout, invalid receipt, or failed anchor remains a failed verification; this harness never converts it to success.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", default="fuelprice")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--replay-chain", action="store_true")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=(
            "verify_dataset_cold", "verify_dataset_warm", "verify_evidence_live_miss",
            "verify_evidence_cache_hit", "verify_attestation_l1", "verify_attestation_l2_replay",
        ),
        help="Repeat to measure only named scenarios; defaults to all representative scenarios.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.samples < 1:
        raise SystemExit("--samples must be at least 1")
    selected = set(args.scenario) if args.scenario else None
    print(json.dumps(asyncio.run(run_benchmark(args.dataset_id, args.samples, args.replay_chain, selected)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
