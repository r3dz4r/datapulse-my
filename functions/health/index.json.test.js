import assert from "node:assert/strict";
import test from "node:test";

import { onRequest } from "./index.json.js";

const request = binding => onRequest({ env: { DATAPULSE_HEALTH_INDEX: binding } });

test("populated binding returns 200 and the exact bytes", async () => {
  const expected = new Uint8Array([0x7b, 0x22, 0x6f, 0x6b, 0x22, 0x3a, 0x74, 0x72, 0x75, 0x65, 0x7d]);
  const response = await request({
    get: async (key, type) => {
      assert.equal(key, "health-index.json");
      assert.equal(type, "arrayBuffer");
      return expected.buffer;
    },
  });

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Content-Type"), "application/json");
  assert.equal(response.headers.get("Cache-Control"), "public, max-age=60");
  assert.deepEqual(new Uint8Array(await response.arrayBuffer()), expected);
});

test("empty or missing binding returns 503", async () => {
  const empty = await request({ get: async () => new ArrayBuffer(0) });
  const missing = await onRequest({ env: {} });

  for (const response of [empty, missing]) {
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("Content-Type"), "application/json");
    assert.equal(response.headers.get("Cache-Control"), "no-store");
    assert.equal(await response.text(), '{"error":"health index unavailable"}');
  }
});

test("binding whose read throws returns 503", async () => {
  const response = await request({ get: async () => { throw new Error("offline fixture failure"); } });

  assert.equal(response.status, 503);
  assert.equal(response.headers.get("Content-Type"), "application/json");
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.equal(await response.text(), '{"error":"health index unavailable"}');
});
