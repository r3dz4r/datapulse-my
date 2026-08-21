"""Durable, lock-protected paid entitlement state (no plaintext credentials)."""
from __future__ import annotations

import base64
import calendar
import fcntl
import hashlib
import hmac
import json
import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or utcnow()).isoformat().replace("+00:00", "Z")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _next_month(value: datetime) -> datetime:
    """Advance a monthly billing boundary while preserving its UTC wall time."""
    year, month = value.year, value.month + 1
    if month == 13:
        year, month = year + 1, 1
    # Billing endpoints supplied by Paddle are valid monthly boundaries.  Clamping
    # protects legacy records such as a 31st from making quota checks fail closed.
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


class Entitlements:
    """JSON state with advisory inter-process locking and atomic replacement."""

    def __init__(self, path: Path, key_salt: str):
        self.path = path
        self.key_salt = key_salt

    @contextmanager
    def transaction(self) -> Iterator[dict[str, Any]]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                try:
                    state = json.loads(self.path.read_text(encoding="utf-8"))
                except FileNotFoundError:
                    state = {}
                state.setdefault("entitlements", {})
                state.setdefault("ledger", {})
                state.setdefault("redemptions", {})
                yield state
                temporary = self.path.with_suffix(self.path.suffix + ".tmp")
                temporary.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                os.replace(temporary, self.path)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _key_hash(self, key: str) -> str:
        return digest(self.key_salt + ":" + key)

    def _recovery_key(self, nonce: str) -> str:
        """Derive an opaque key so a lost response can be safely replayed."""
        material = hmac.new(self.key_salt.encode("utf-8"), nonce.encode("utf-8"), hashlib.sha256).digest()
        return "dp_" + base64.urlsafe_b64encode(material).decode("ascii").rstrip("=")

    @staticmethod
    def _period_end(data: dict[str, Any]) -> str | None:
        for name in ("current_billing_period", "billing_period"):
            period = data.get(name)
            if isinstance(period, dict) and isinstance(period.get("ends_at"), str):
                return period["ends_at"]
        return None

    @staticmethod
    def _identity(data: dict[str, Any], event_type: str) -> str:
        if event_type in {"adjustment.created", "adjustment.updated"}:
            return str(data.get("subscription_id") or "")
        return str(data.get("subscription_id") or data.get("id") or "")

    @staticmethod
    def _is_effective_revoking_adjustment(data: dict[str, Any]) -> bool:
        """Only apply an adjustment once Paddle has made its revocation final."""
        action = data.get("action")
        status = data.get("status")
        return action in {"refund", "chargeback", "chargeback_warning"} and status == "approved"

    @staticmethod
    def _newer_period(entitlement: dict[str, Any], period_end: str) -> bool:
        previous = entitlement.get("reset_at")
        return not isinstance(previous, str) or _parse_time(period_end) > _parse_time(previous)

    def _advance_quota_period(self, entitlement: dict[str, Any], now: datetime) -> None:
        reset_at = entitlement.get("reset_at")
        if not isinstance(reset_at, str):
            return
        boundary = _parse_time(reset_at)
        if boundary > now:
            return
        while boundary <= now:
            boundary = _next_month(boundary)
        entitlement["used"] = 0
        entitlement["reset_at"] = iso(boundary)

    def apply_event(
        self,
        event_id: str,
        event_type: str,
        payload_hash: str,
        data: dict[str, Any],
        now: datetime | None = None,
    ) -> str:
        """Apply an already-verified event without returning its redemption nonce."""
        now = now or utcnow()
        with self.transaction() as state:
            previous = state["ledger"].get(event_id)
            if previous:
                return "security_failure" if previous["payload_hash"] != payload_hash else "duplicate"

            opaque_id = self._identity(data, event_type)
            outcome = "ignored"
            if opaque_id:
                entitlement = state["entitlements"].get(opaque_id)
                activating = {"subscription.activated", "subscription.created", "subscription.updated", "subscription.resumed", "subscription.renewed", "transaction.completed"}
                update_status = data.get("status") if event_type == "subscription.updated" else None
                if event_type == "subscription.updated" and update_status == "past_due":
                    entitlement = entitlement or {"key_hash": None, "paddle_id": opaque_id, "scopes": ["npra.read"], "tier": "pro", "used": 0}
                    state["entitlements"][opaque_id] = entitlement
                    if entitlement.get("status") != "revoked":
                        entitlement.update({"status": "suspended", "updated_at": iso(now)})
                        outcome = "suspended"
                elif event_type == "subscription.updated" and update_status == "paused":
                    if entitlement and entitlement.get("status") != "revoked":
                        entitlement.update({"status": "paused", "updated_at": iso(now)})
                        outcome = "paused"
                elif event_type == "subscription.updated" and update_status == "canceled":
                    entitlement = entitlement or {"key_hash": None, "paddle_id": opaque_id, "scopes": ["npra.read"], "tier": "pro", "used": 0}
                    state["entitlements"][opaque_id] = entitlement
                    entitlement.update({"status": "revoked", "updated_at": iso(now)})
                    outcome = "revoked"
                elif event_type in activating and (event_type != "subscription.updated" or update_status in {None, "active"}):
                    if entitlement is None and event_type not in {"subscription.activated", "subscription.created", "transaction.completed"}:
                        outcome = "ignored"
                    else:
                        entitlement = entitlement or {"key_hash": None, "paddle_id": opaque_id, "scopes": ["npra.read"], "tier": "pro", "used": 0}
                        state["entitlements"][opaque_id] = entitlement
                        # A cancelled/refunded subscription is terminal. A new verified
                        # subscription has a different Paddle identity and gets its own record.
                        can_resume = event_type != "subscription.resumed" or entitlement.get("status") == "paused"
                        if entitlement.get("status") != "revoked" and can_resume:
                            period_end = self._period_end(data)
                            entitlement.update({"quota": 100000, "status": "active", "updated_at": iso(now)})
                            if period_end and self._newer_period(entitlement, period_end):
                                entitlement["reset_at"] = period_end
                                entitlement["used"] = 0
                            custom_data = data.get("custom_data")
                            nonce = custom_data.get("dp_nonce") if isinstance(custom_data, dict) else None
                            if isinstance(nonce, str) and len(nonce) >= 32:
                                state["redemptions"].setdefault(
                                    digest(nonce),
                                    {"expires_at": iso(now + timedelta(minutes=15)), "paddle_id": opaque_id, "used": False},
                                )
                            outcome = "activated"
                elif event_type == "subscription.past_due":
                    entitlement = entitlement or {"key_hash": None, "paddle_id": opaque_id, "scopes": ["npra.read"], "tier": "pro", "used": 0}
                    state["entitlements"][opaque_id] = entitlement
                    entitlement.update({"status": "suspended", "updated_at": iso(now)})
                    outcome = "suspended"
                elif event_type == "subscription.paused":
                    if entitlement:
                        entitlement.update({"status": "paused", "updated_at": iso(now)})
                        outcome = "paused"
                elif event_type == "subscription.canceled" or (
                    event_type in {"adjustment.created", "adjustment.updated"}
                    and self._is_effective_revoking_adjustment(data)
                ):
                    entitlement = entitlement or {"key_hash": None, "paddle_id": opaque_id, "scopes": ["npra.read"], "tier": "pro", "used": 0}
                    state["entitlements"][opaque_id] = entitlement
                    entitlement.update({"status": "revoked", "updated_at": iso(now)})
                    outcome = "revoked"
            state["ledger"][event_id] = {"event_type": event_type, "outcome": outcome, "payload_hash": payload_hash, "received_at": iso(now)}
            return outcome

    def redeem(self, nonce: str, now: datetime | None = None) -> tuple[str, str | None]:
        """Issue or recover one deterministic key during the short redemption window."""
        now = now or utcnow()
        with self.transaction() as state:
            record = state["redemptions"].get(digest(nonce))
            if not record:
                return "pending", None
            if _parse_time(record["expires_at"]) <= now:
                return "invalid", None
            entitlement = state["entitlements"].get(record["paddle_id"])
            if not entitlement or entitlement.get("status") != "active":
                return "invalid", None
            key = self._recovery_key(nonce)
            if entitlement.get("key_hash"):
                if secrets.compare_digest(str(entitlement["key_hash"]), self._key_hash(key)):
                    return "recovered", key
                return "invalid", None
            entitlement["key_hash"] = self._key_hash(key)
            entitlement["updated_at"] = iso(now)
            record["used"] = True
            return "issued", key

    def by_key(self, key: str, now: datetime | None = None) -> dict[str, Any] | None:
        now = now or utcnow()
        target = self._key_hash(key)
        with self.transaction() as state:
            for item in state["entitlements"].values():
                if secrets.compare_digest(str(item.get("key_hash") or ""), target):
                    self._advance_quota_period(item, now)
                    return dict(item)
        return None

    def charge(self, key: str, now: datetime | None = None) -> tuple[str, dict[str, Any] | None]:
        now = now or utcnow()
        target = self._key_hash(key)
        with self.transaction() as state:
            for item in state["entitlements"].values():
                if secrets.compare_digest(str(item.get("key_hash") or ""), target):
                    if item.get("status") != "active":
                        return "inactive", dict(item)
                    self._advance_quota_period(item, now)
                    if int(item.get("used", 0)) >= int(item.get("quota", 100000)):
                        return "quota_exhausted", dict(item)
                    item["used"] = int(item.get("used", 0)) + 1
                    return "charged", dict(item)
        return "invalid", None

    def refund(self, key: str) -> None:
        target = self._key_hash(key)
        with self.transaction() as state:
            for item in state["entitlements"].values():
                if secrets.compare_digest(str(item.get("key_hash") or ""), target):
                    item["used"] = max(0, int(item.get("used", 0)) - 1)
                    return
