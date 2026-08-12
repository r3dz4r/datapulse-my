"""Stdlib integration tests for the authenticated buyer API."""
from __future__ import annotations
import http.client, json, tempfile, threading, time, unittest
from datetime import datetime, timezone
from pathlib import Path
from api.config import Config
from api.keys import add_key, read_keys, revoke_key
from api.server import make_server, RateLimiter

class BuyerApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root / "health").mkdir(); (self.root / "deltas").mkdir()
        datasets = [{"dataset_id": f"d{i}", "status": "fresh"} for i in range(3)]
        (self.root / "health/latest.json").write_text(json.dumps({"checked_at":"2026-08-12T00:00:00Z","datasets":datasets}))
        (self.root / "health/history.jsonl").write_text("\n".join(json.dumps({"dataset_id":"d0","observed_at":"2026-08-%02dT00:00:00Z" % day}) for day in range(1, 13)) + "\n")
        for cycle in ("2026-08-10T10:00", "2026-08-12T10:00"):
            (self.root / "deltas" / (cycle + ".json")).write_text(json.dumps({"cycle":cycle,"observed_at":cycle + ":00Z"}))
        (self.root / "catalog-snapshot.json").write_text(json.dumps({"datasets": datasets}))
        self.config = Config(self.root, self.root / "keys.json", self.root / "rate.json", 100, "127.0.0.1", 0, self.root / "audit.jsonl", 2, "test-salt")
        self.token = add_key(self.config.keys_file, "test", ["datasets.read", "deltas.read"], self.config.key_salt)
        self.server = make_server(self.config); self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
    def tearDown(self): self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()
    def request(self, path, key=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3); headers = {"X-API-Key":self.token} if key else {}
        conn.request("GET", path, headers=headers); response = conn.getresponse(); body = json.loads(response.read()); headers = dict(response.getheaders()); conn.close(); return response.status, body, headers
    def test_health_requires_key(self): self.assertEqual(self.request("/api/v1/health", False)[0], 401)
    def test_health_with_valid_key(self): self.assertEqual(self.request("/api/v1/health")[0], 200)
    def test_datasets_list_paginated(self):
        status, body, _ = self.request("/api/v1/datasets?limit=2"); self.assertEqual((status, len(body["data"]), body["pagination"]["next_cursor"]), (200,2,"2"))
    def test_dataset_history_respects_window(self):
        status, body, _ = self.request("/api/v1/datasets/d0/history?days=5"); self.assertEqual(status, 200); self.assertLessEqual(len(body["data"]), 5)
    def test_deltas_window(self):
        status, body, _ = self.request("/api/v1/deltas?from=2026-08-11&to=2026-08-13"); self.assertEqual([x["cycle"] for x in body["data"]], ["2026-08-12T10:00"])
    def test_deltas_404_unknown_cycle(self): self.assertEqual(self.request("/api/v1/deltas/nope")[0], 404)
    def test_errors_have_envelope(self):
        for path, key in (("/api/v1/health",False),("/api/v1/nope",True)):
            _, body, _ = self.request(path,key); self.assertIn("code", body["error"]); self.assertIn("message", body["error"])
    def test_rate_limit_token_bucket(self):
        self.server.app.rate_limiter = RateLimiter(self.config.rate_state_file, 100)
        responses = [self.request("/api/v1/health")[0] for _ in range(101)]; self.assertEqual(responses[-1], 429)
    def test_rate_limit_persists(self):
        limiter = RateLimiter(self.config.rate_state_file, 1); self.assertTrue(limiter.allow("x")[0]); self.assertFalse(RateLimiter(self.config.rate_state_file,1).allow("x")[0])
    def test_audit_log_written(self):
        self.request("/api/v1/health"); time.sleep(.05); entry = json.loads(self.config.audit_log.read_text().splitlines()[-1]); self.assertEqual((entry["status"],entry["key_label"],entry["path"]),(200,"test","/api/v1/health"))
    def test_audit_log_includes_401(self):
        self.request("/api/v1/health",False); time.sleep(.05); self.assertEqual(json.loads(self.config.audit_log.read_text().splitlines()[-1])["status"],401)
    def test_audit_appends_not_overwrites(self):
        self.request("/api/v1/health"); self.request("/api/v1/health"); time.sleep(.05); self.assertEqual(len(self.config.audit_log.read_text().splitlines()),2)
    def test_api_keys_lifecycle(self):
        token = add_key(self.config.keys_file, "later", ["datasets.read"], self.config.key_salt); self.assertTrue(read_keys(self.config.keys_file)["active"]); self.assertTrue(revoke_key(self.config.keys_file,"later")); self.assertEqual(len(read_keys(self.config.keys_file)["revoked"]),1)
    def test_revoked_key_is_rejected(self):
        self.assertTrue(revoke_key(self.config.keys_file, "test")); self.assertEqual(self.request("/api/v1/health")[0], 401)
    def test_api_keys_dup_token_uniqueness(self):
        tokens = {add_key(self.config.keys_file,"same",["datasets.read"],self.config.key_salt) for _ in range(100)}; self.assertEqual(len(tokens),100)
    def test_structured_error_envelope(self):
        self.server.app.rate_limiter = RateLimiter(self.config.rate_state_file, 1); self.request("/api/v1/health"); status, body, headers = self.request("/api/v1/health"); self.assertEqual(status,429); self.assertIn("retry_after_s", body["error"]); self.assertIn("Retry-After",headers)

if __name__ == "__main__": unittest.main()
