"""Offline security contract tests for the NPRA paid control plane."""
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from api.config import Config
from api.entitlements import Entitlements
from api.paddle import (
    SANDBOX_PRICE_ID,
    SANDBOX_PRODUCT_ID,
    PaddleError,
    parse_approved_event,
    verify_signature,
)
from api.pharma_proxy import fetch
from api.server import make_server


def payload(
    event_id: str = "evt_1",
    event_type: str = "transaction.completed",
    price: str = SANDBOX_PRICE_ID,
    subscription_id: str = "sub_1",
    nonce: str = "n" * 43,
    subscription_status: str | None = None,
) -> bytes:
    data = {
        "id": "txn_1" if event_type == "transaction.completed" else subscription_id,
        "subscription_id": subscription_id if event_type == "transaction.completed" else None,
        "custom_data": {"dp_nonce": nonce},
        "items": [{"price": {"id": price, "product": {"id": SANDBOX_PRODUCT_ID}}}],
        "billing_period": {"ends_at": "2026-02-01T00:00:00Z"},
    }
    if subscription_status is not None:
        data["status"] = subscription_status
    return json.dumps(
        {"event_id": event_id, "event_type": event_type, "occurred_at": "2026-01-01T00:00:00Z", "data": data},
        separators=(",", ":"),
    ).encode()


def adjustment_payload(
    event_id: str,
    event_type: str,
    action: str,
    status: str,
    subscription_id: str = "sub_1",
    adjustment_id: str = "adj_1",
) -> bytes:
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": "2026-01-01T00:00:00Z",
            "data": {
                "id": adjustment_id,
                "subscription_id": subscription_id,
                "action": action,
                "status": status,
            },
        },
        separators=(",", ":"),
    ).encode()


class PaddleContractTest(unittest.TestCase):
    def test_transaction_completed_accepts_verified_flat_product_id(self) -> None:
        raw = json.dumps(
            {
                "event_id": "evt_transaction_completed_flat_product",
                "event_type": "transaction.completed",
                "occurred_at": "2026-01-01T00:00:00Z",
                "data": {
                    "id": "txn_flat_product",
                    "items": [{"price": {"id": SANDBOX_PRICE_ID, "product_id": SANDBOX_PRODUCT_ID}}],
                },
            },
            separators=(",", ":"),
        ).encode()

        event_id, event_type, data, _ = parse_approved_event(raw)

        self.assertEqual(event_id, "evt_transaction_completed_flat_product")
        self.assertEqual(event_type, "transaction.completed")
        self.assertEqual(data["id"], "txn_flat_product")

    def test_signature_is_exact_body_and_timestamp_bound(self) -> None:
        raw, secret, timestamp = payload(), "fake-webhook-secret", 1_700_000_000
        signature = hmac.new(secret.encode(), str(timestamp).encode() + b":" + raw, hashlib.sha256).hexdigest()
        verify_signature(raw, f"ts={timestamp};h1={signature}", secret, now=timestamp)
        with self.assertRaises(PaddleError):
            verify_signature(raw + b" ", f"ts={timestamp};h1={signature}", secret, now=timestamp)
        with self.assertRaises(PaddleError):
            verify_signature(raw, f"ts={timestamp};h1={signature}", secret, now=timestamp + 301)

    def test_each_real_lifecycle_name_is_accepted_and_offer_gated(self) -> None:
        for event_type in (
            "subscription.created",
            "subscription.activated",
            "subscription.updated",
            "subscription.paused",
            "subscription.resumed",
            "subscription.canceled",
            "transaction.completed",
        ):
            with self.subTest(event_type=event_type):
                parse_approved_event(payload(event_type=event_type))
        for event_type in ("adjustment.created", "adjustment.updated"):
            with self.subTest(event_type=event_type):
                parse_approved_event(adjustment_payload("evt_adjustment", event_type, "refund", "pending_approval"))
        adjustment_without_subscription = json.dumps(
            {
                "event_id": "evt_bad_adjustment",
                "event_type": "adjustment.updated",
                "occurred_at": "2026-01-01T00:00:00Z",
                "data": {"id": "adj_only", "action": "refund", "status": "approved"},
            },
            separators=(",", ":"),
        ).encode()
        with self.assertRaises(PaddleError):
            parse_approved_event(adjustment_without_subscription)
        with self.assertRaises(PaddleError):
            parse_approved_event(payload(price="pri_wrong"))
        with self.assertRaises(PaddleError):
            parse_approved_event(payload(event_type="subscription.activated", price="pri_wrong"))


class DurableEntitlementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = Entitlements(Path(self.temp.name) / "state.json", "fake-salt")
        self.raw = payload()
        self.event_id, self.event_type, self.data, self.hash = parse_approved_event(self.raw)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def activate(self, event_id: str = "evt_1", nonce: str = "n" * 43, subscription_id: str = "sub_1") -> str:
        raw = payload(event_id=event_id, nonce=nonce, subscription_id=subscription_id)
        _, event_type, data, payload_hash = parse_approved_event(raw)
        return self.store.apply_event(event_id, event_type, payload_hash, data)

    def test_lifecycle_replay_conflict_is_recorded(self) -> None:
        self.assertEqual(self.activate(), "activated")
        state = json.loads(self.store.path.read_text())
        self.assertNotIn("n" * 43, json.dumps(state))
        self.assertIn(hashlib.sha256(("n" * 43).encode()).hexdigest(), state["redemptions"])
        self.assertEqual(self.store.apply_event(self.event_id, self.event_type, self.hash, self.data), "duplicate")
        self.assertEqual(self.store.apply_event(self.event_id, self.event_type, "different", self.data), "security_failure")

    def test_subscription_activated_provisions_once_and_replays(self) -> None:
        raw = payload(event_id="evt_activated", event_type="subscription.activated")
        event_id, event_type, data, payload_hash = parse_approved_event(raw)
        self.assertEqual(self.store.apply_event(event_id, event_type, payload_hash, data), "activated")
        self.assertIn("sub_1", json.loads(self.store.path.read_text())["entitlements"])
        self.assertEqual(self.store.apply_event(event_id, event_type, payload_hash, data), "duplicate")

    def test_pending_and_rejected_refunds_do_not_revoke_entitlement(self) -> None:
        self.assertEqual(self.activate(), "activated")
        for event_id, event_type, status in (
            ("evt_refund_pending", "adjustment.created", "pending_approval"),
            ("evt_refund_rejected", "adjustment.updated", "rejected"),
        ):
            raw = adjustment_payload(event_id, event_type, "refund", status)
            _, _, data, payload_hash = parse_approved_event(raw)
            self.assertEqual(self.store.apply_event(event_id, event_type, payload_hash, data), "ignored")
        self.assertEqual(json.loads(self.store.path.read_text())["entitlements"]["sub_1"]["status"], "active")

    def test_approved_refund_and_effective_chargeback_revoke_subscription_not_adjustment(self) -> None:
        self.assertEqual(self.activate(), "activated")
        raw = adjustment_payload("evt_refund_approved", "adjustment.updated", "refund", "approved", adjustment_id="adj_refund")
        _, event_type, data, payload_hash = parse_approved_event(raw)
        self.assertEqual(self.store.apply_event("evt_refund_approved", event_type, payload_hash, data), "revoked")
        state = json.loads(self.store.path.read_text())
        self.assertEqual(state["entitlements"]["sub_1"]["status"], "revoked")
        self.assertNotIn("adj_refund", state["entitlements"])

        self.assertEqual(self.activate(event_id="evt_second", subscription_id="sub_2"), "activated")
        raw = adjustment_payload("evt_chargeback", "adjustment.created", "chargeback", "approved", subscription_id="sub_2", adjustment_id="adj_chargeback")
        _, event_type, data, payload_hash = parse_approved_event(raw)
        self.assertEqual(self.store.apply_event("evt_chargeback", event_type, payload_hash, data), "revoked")
        state = json.loads(self.store.path.read_text())
        self.assertNotIn("adj_chargeback", state["entitlements"])
        self.assertEqual(state["entitlements"]["sub_2"]["status"], "revoked")

    def test_pause_resume_reactivates_only_same_verified_subscription(self) -> None:
        self.assertEqual(self.activate(), "activated")
        for event_id, event_type, expected in (("evt_pause", "subscription.paused", "paused"), ("evt_resume", "subscription.resumed", "activated")):
            raw = payload(event_id=event_id, event_type=event_type)
            _, _, data, payload_hash = parse_approved_event(raw)
            self.assertEqual(self.store.apply_event(event_id, event_type, payload_hash, data), expected)
        outcome, key = self.store.redeem("n" * 43)
        self.assertEqual((outcome, key is not None), ("issued", True))
        canceled = {"id": "sub_1"}
        self.assertEqual(self.store.apply_event("evt_cancel", "subscription.canceled", "h2", canceled), "revoked")
        raw = payload(event_id="evt_bad_resume", event_type="subscription.resumed")
        _, _, data, payload_hash = parse_approved_event(raw)
        self.assertEqual(self.store.apply_event("evt_bad_resume", "subscription.resumed", payload_hash, data), "ignored")
        self.assertEqual(self.store.charge(key or "")[0], "inactive")

    def test_status_bearing_subscription_updates_follow_lifecycle_state(self) -> None:
        for status, expected_status, expected_outcome in (
            ("active", "active", "activated"),
            ("past_due", "suspended", "suspended"),
            ("paused", "paused", "paused"),
            ("canceled", "revoked", "revoked"),
        ):
            with self.subTest(status=status):
                subscription_id = f"sub_update_{status}"
                nonce = (status + "_" + ("x" * 43))[:43]
                self.assertEqual(self.activate(f"evt_activate_{status}", nonce, subscription_id), "activated")
                _, key = self.store.redeem(nonce)
                raw = payload(
                    event_id=f"evt_update_{status}",
                    event_type="subscription.updated",
                    subscription_id=subscription_id,
                    nonce=nonce,
                    subscription_status=status,
                )
                event_id, event_type, data, payload_hash = parse_approved_event(raw)
                self.assertEqual(self.store.apply_event(event_id, event_type, payload_hash, data), expected_outcome)
                self.assertEqual(self.store.by_key(key or "")["status"], expected_status)
                self.assertEqual(self.store.charge(key or "")[0], "charged" if status == "active" else "inactive")

    def test_terminal_subscription_update_cannot_reactivate_access(self) -> None:
        self.assertEqual(self.activate(), "activated")
        _, key = self.store.redeem("n" * 43)
        self.assertEqual(self.store.apply_event("evt_cancel", "subscription.canceled", "h2", {"id": "sub_1"}), "revoked")
        raw = payload(event_id="evt_active_after_cancel", event_type="subscription.updated", subscription_status="active")
        event_id, event_type, data, payload_hash = parse_approved_event(raw)
        self.assertEqual(self.store.apply_event(event_id, event_type, payload_hash, data), "ignored")
        self.assertEqual(self.store.by_key(key or "")["status"], "revoked")
        self.assertEqual(self.store.charge(key or "")[0], "inactive")

    def test_unknown_status_bearing_subscription_update_is_ignored(self) -> None:
        self.assertEqual(self.activate(), "activated")
        _, key = self.store.redeem("n" * 43)
        raw = payload(event_id="evt_unknown_update", event_type="subscription.updated", subscription_status="trialing")
        event_id, event_type, data, payload_hash = parse_approved_event(raw)
        self.assertEqual(self.store.apply_event(event_id, event_type, payload_hash, data), "ignored")
        self.assertEqual(self.store.by_key(key or "")["status"], "active")
        self.assertEqual(self.store.charge(key or "")[0], "charged")

    def test_resume_cannot_create_access_for_an_unverified_paused_identity(self) -> None:
        self.assertEqual(self.store.apply_event("evt_pause", "subscription.paused", "h1", {"id": "sub_unknown"}), "ignored")
        raw = payload(event_id="evt_resume", event_type="subscription.resumed", subscription_id="sub_unknown")
        _, event_type, data, payload_hash = parse_approved_event(raw)
        self.assertEqual(self.store.apply_event("evt_resume", event_type, payload_hash, data), "ignored")

    def test_lost_redemption_response_recovers_same_key_only_for_same_nonce(self) -> None:
        self.assertEqual(self.activate(), "activated")
        outcome, key = self.store.redeem("n" * 43)
        self.assertEqual(outcome, "issued")
        self.assertEqual(self.store.redeem("n" * 43), ("recovered", key))
        self.assertEqual(self.store.redeem("x" * 43), ("pending", None))

    def test_expired_quota_advances_boundary_before_every_charge(self) -> None:
        self.assertEqual(self.activate(), "activated")
        _, key = self.store.redeem("n" * 43)
        with self.store.transaction() as state:
            entitlement = state["entitlements"]["sub_1"]
            entitlement.update({"quota": 1, "reset_at": "2026-01-01T00:00:00Z", "used": 1})
        now = datetime(2026, 3, 15, tzinfo=timezone.utc)
        self.assertEqual(self.store.charge(key or "", now)[0], "charged")
        self.assertEqual(self.store.charge(key or "", now)[0], "quota_exhausted")
        record = self.store.by_key(key or "", now)
        self.assertEqual(record and record["reset_at"], "2026-04-01T00:00:00Z")

    def test_malformed_existing_state_fails_closed_without_replacement(self) -> None:
        malformed = "{not valid JSON"
        self.store.path.write_text(malformed, encoding="utf-8")

        with self.assertRaises(json.JSONDecodeError):
            self.store.charge("any-key")

        self.assertEqual(self.store.path.read_text(encoding="utf-8"), malformed)


class WebhookReplayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        config = Config(root, root / "keys.json", root / "rate.json", 10, "127.0.0.1", 0, root / "audit.jsonl", 10, "fake-salt", root / "entitlements.json", "fake-webhook-secret")
        self.server = make_server(config)
        import threading

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def post(self, raw: bytes) -> tuple[int, dict[str, object]]:
        timestamp = 1_700_000_000
        signature = hmac.new(b"fake-webhook-secret", str(timestamp).encode() + b":" + raw, hashlib.sha256).hexdigest()
        with patch("api.paddle.time.time", return_value=timestamp):
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
            connection.request("POST", "/api/v1/paddle/webhook", raw, {"Paddle-Signature": f"ts={timestamp};h1={signature}"})
            response = connection.getresponse()
            body = json.loads(response.read())
            connection.close()
        return response.status, body

    def test_identical_replay_is_ok_but_conflicting_replay_is_409_and_audited(self) -> None:
        raw = payload()
        self.assertEqual(self.post(raw)[0], 200)
        self.assertEqual(self.post(raw)[0], 200)
        changed = payload(nonce="x" * 43)
        # Signatures are valid for both payloads; the event-id conflict is the test.
        status, body = self.post(changed)
        self.assertEqual((status, body["error"]["code"]), (409, "webhook_replay_conflict"))
        self.assertIn("webhook_replay_payload_conflict", (Path(self.temp.name) / "audit.jsonl").read_text())


class ProxyContractTest(unittest.TestCase):
    def test_headers_are_isolated_and_scheme_selects_matching_connection(self) -> None:
        requests: list[tuple[str, int, dict[str, str]]] = []

        class Response:
            status = 200

            def read(self, _size: int) -> bytes:
                return b'{}'

            def getheader(self, _name: str, _default: str = "") -> str:
                return "application/json"

        class Connection:
            def __init__(self, host: str, port: int, timeout: int) -> None:
                self.host, self.port = host, port

            def request(self, _method: str, _path: str, headers: dict[str, str]) -> None:
                requests.append((self.host, self.port, headers))

            def getresponse(self) -> Response:
                return Response()

            def close(self) -> None:
                pass

        with patch("api.pharma_proxy.HTTPSConnection", Connection), patch("api.pharma_proxy.HTTPConnection", Connection):
            self.assertEqual(fetch("https://engine.example:8443/base", "internal-only", "health"), (200, {}))
        _, port, headers = requests[0]
        self.assertEqual(port, 8443)
        self.assertEqual(headers, {"Accept": "application/json", "X-API-Key": "internal-only"})

    def test_http_uses_http_connection_and_rejects_unsafe_engine_urls(self) -> None:
        with patch("api.pharma_proxy.HTTPConnection") as http_connection, patch("api.pharma_proxy.HTTPSConnection") as https_connection:
            connection = http_connection.return_value
            response = connection.getresponse.return_value
            response.status = 200
            response.read.return_value = b"{}"
            response.getheader.return_value = "application/json"
            fetch("http://engine.example", "internal-only", "health")
            http_connection.assert_called_once()
            https_connection.assert_not_called()
        with self.assertRaises(RuntimeError):
            fetch("ftp://engine.example", "internal-only", "health")


class NPRADispatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        config = Config(
            root, root / "keys.json", root / "rate.json", 100, "127.0.0.1", 0,
            root / "audit.jsonl", 100, "fake-salt", root / "entitlements.json", "",
            "internal-only", "https://engine.example",
        )
        self.server = make_server(config)
        self.assertEqual(self.server.app.entitlements.apply_event("evt_pro", "transaction.completed", "payload", {
            "id": "txn_pro", "subscription_id": "sub_pro", "custom_data": {"dp_nonce": "n" * 43},
            "billing_period": {"ends_at": "2026-02-01T00:00:00Z"},
        }), "activated")
        outcome, self.key = self.server.app.entitlements.redeem("n" * 43)
        self.assertEqual(outcome, "issued")
        import threading

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def get(self, path: str) -> tuple[int, dict[str, object]]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request("GET", path, headers={"X-API-Key": self.key or ""})
        response = connection.getresponse()
        body = json.loads(response.read())
        connection.close()
        return response.status, body

    def used(self) -> int:
        record = self.server.app.entitlements.by_key(self.key or "")
        return int(record["used"]) if record else -1

    def test_upstream_failures_refund_once_and_4xx_is_billable(self) -> None:
        failures: tuple[Exception, ...] = (
            OSError("transport"),
            RuntimeError("upstream response too large"),
            RuntimeError("invalid upstream response"),
            RuntimeError("upstream failure"),
            json.JSONDecodeError("malformed JSON", "{", 1),
            ValueError("malformed response"),
        )
        for failure in failures:
            with self.subTest(failure=str(failure)), patch("api.server.pharma_fetch", side_effect=failure), patch.object(self.server.app.entitlements, "refund", wraps=self.server.app.entitlements.refund) as refund:
                self.assertEqual(self.get("/api/v1/npra/health")[0], 503)
                refund.assert_called_once_with(self.key or "")
                self.assertEqual(self.used(), 0)
        with patch("api.server.pharma_fetch", return_value=(404, {"error": "not found"})):
            self.assertEqual(self.get("/api/v1/npra/health")[0], 404)
        self.assertEqual(self.used(), 1)

    def test_returned_upstream_5xx_refunds_once(self) -> None:
        with patch("api.server.pharma_fetch", return_value=(503, {"error": "unavailable"})), patch.object(
            self.server.app.entitlements,
            "refund",
            wraps=self.server.app.entitlements.refund,
        ) as refund:
            self.assertEqual(self.get("/api/v1/npra/health")[0], 503)
            refund.assert_called_once_with(self.key or "")
        self.assertEqual(self.used(), 0)

    def test_collection_routes_are_exact(self) -> None:
        with patch("api.server.pharma_fetch", return_value=(200, {"ok": True})) as upstream:
            self.assertEqual(self.get("/api/v1/npra/health")[0], 200)
            self.assertEqual(self.get("/api/v1/npra/changes")[0], 200)
            self.assertEqual(self.get("/api/v1/npra/health/extra")[0], 404)
            self.assertEqual(self.get("/api/v1/npra/changes/extra")[0], 404)
        self.assertEqual(upstream.call_count, 2)

    def test_lookup_routes_reject_extra_segments_before_quota_charge(self) -> None:
        with patch("api.server.pharma_fetch") as upstream:
            for resource in ("product", "manufacturer", "importer"):
                with self.subTest(resource=resource):
                    self.assertEqual(self.get(f"/api/v1/npra/{resource}/id/extra")[0], 404)
                    self.assertEqual(self.used(), 0)
        upstream.assert_not_called()


def test_checkout_shell_is_safe_idempotent_and_preserves_existing_token() -> None:
    from scripts.embed_dashboard_data import _npra_checkout_shell

    fake_token = "test_public_</script>&_token"
    output = _npra_checkout_shell("<main></main>", fake_token)
    preserved = _npra_checkout_shell(output)
    assert preserved.count("<!-- NPRA-PADDLE-CHECKOUT -->") == 1
    assert "\\u003c/script\\u003e\\u0026" in output
    assert "maxRedeemAttempts = 10" in output
    assert "result.error.code === 'redemption_pending'" in output
    assert "response.status === 409) return setTimeout" not in output
    assert "localStorage" not in output
    assert "PADDLE_SANDBOX_WEBHOOK_SECRET" not in output
    assert "PADDLE_SANDBOX_API_KEY" not in output
    assert "window.PADDLE_SANDBOX_CLIENT_TOKEN" in preserved


def test_npra_freshness_uses_health_checked_at_separately_from_source_update() -> None:
    from scripts.embed_dashboard_data import _npra_freshness

    html = '<span data-npra-cfd="old">old</span>'
    health = {
        "checked_at": "2026-08-20T15:55:29Z",
        "datasets": [
            {"dataset_id": "pharmaceutical_products", "status": "fresh", "last_modified": "2026-08-01T00:00:00Z"},
            {"dataset_id": "pharmaceutical_products_cancelled", "status": "stale", "last_modified": "2026-08-19T00:00:00Z"},
        ],
    }
    updated = _npra_freshness(html, health)
    assert 'data-npra-cfd="2026-08-20T15:55:29Z"' in updated
    assert "last checked 20 Aug 2026, 11:55 pm MYT" in updated
    assert "Latest source update: 19 Aug 2026, 8:00 am MYT" in updated
