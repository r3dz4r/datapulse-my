"""Paddle Billing webhook verification and exact sandbox offer gating."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

SANDBOX_PRODUCT_ID = "pro_01m0ftxen762hpbz6bv8z7t7c0"
SANDBOX_PRICE_ID = "pri_01m0fvdratkz274ker6v7y70x3"
MAX_BODY_BYTES = 256 * 1024
ACTIVATING_EVENTS = {
    "subscription.activated",
    "subscription.created",
    "subscription.updated",
    "subscription.resumed",
    "subscription.renewed",  # Legacy compatibility only.
    "transaction.completed",
}
ADJUSTMENT_EVENTS = {"adjustment.created", "adjustment.updated"}
LIFECYCLE_EVENTS = ACTIVATING_EVENTS | {
    "subscription.paused",
    "subscription.past_due",
    "subscription.canceled",
} | ADJUSTMENT_EVENTS


class PaddleError(ValueError):
    """A webhook that must not be acknowledged as successfully processed."""


def verify_signature(raw: bytes, signature: str | None, secret: str, now: int | None = None, tolerance: int = 300) -> None:
    if not secret or len(raw) > MAX_BODY_BYTES or not signature:
        raise PaddleError("invalid webhook")
    parts: dict[str, list[str]] = {}
    for segment in signature.split(";"):
        key, separator, value = segment.strip().partition("=")
        if separator:
            parts.setdefault(key, []).append(value)
    try:
        timestamp = int(parts["ts"][0])
    except (KeyError, ValueError):
        raise PaddleError("invalid webhook") from None
    if abs((now if now is not None else int(time.time())) - timestamp) > tolerance:
        raise PaddleError("invalid webhook")
    expected = hmac.new(secret.encode(), str(timestamp).encode() + b":" + raw, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, value) for value in parts.get("h1", [])):
        raise PaddleError("invalid webhook")


def _identity(data: dict[str, Any]) -> bool:
    return isinstance(data.get("subscription_id") or data.get("id"), str)


def _adjustment_identity(data: dict[str, Any]) -> bool:
    """Adjustments must target their subscription, never their own adj_ identifier."""
    return isinstance(data.get("subscription_id"), str) and bool(data["subscription_id"])


def _approved_offer(data: dict[str, Any]) -> bool:
    items = data.get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        return False
    price = items[0].get("price")
    if not isinstance(price, dict):
        return False
    product_id = price.get("product_id")
    if product_id is None:
        product = price.get("product")
        product_id = product.get("id") if isinstance(product, dict) else product
    return price.get("id") == SANDBOX_PRICE_ID and product_id == SANDBOX_PRODUCT_ID


def parse_approved_event(raw: bytes) -> tuple[str, str, dict[str, Any], str]:
    """Validate a redacted Paddle event before it can mutate entitlement state."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise PaddleError("invalid webhook") from None
    required = ("event_id", "event_type", "occurred_at")
    if not isinstance(payload, dict) or not all(isinstance(payload.get(field), str) for field in required) or not isinstance(payload.get("data"), dict):
        raise PaddleError("invalid webhook")
    event_type = payload["event_type"]
    data = payload["data"]
    if event_type in ADJUSTMENT_EVENTS and not _adjustment_identity(data):
        raise PaddleError("invalid lifecycle event")
    if event_type in LIFECYCLE_EVENTS and not _identity(data):
        raise PaddleError("invalid lifecycle event")
    if event_type in ACTIVATING_EVENTS and not _approved_offer(data):
        raise PaddleError("unapproved offer")
    return payload["event_id"], event_type, data, hashlib.sha256(raw).hexdigest()
