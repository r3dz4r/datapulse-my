import assert from "node:assert/strict";
import test from "node:test";

import { onRequest } from "./index.json.js";

const request = (binding, assets) => onRequest({
  request: new Request("https://data-pulse.test/health/index.json"),
  env: { DATAPULSE_HEALTH_INDEX: binding, ASSETS: assets },
});

test("health index serves the assembled accepted report through the static binding", async () => {
  const accepted = '{"checked_at":"accepted","datasets":[]}';
  const response = await request({ get: async () => { throw new Error("KV must not be read"); } }, {
    fetch: async url => {
      assert.equal(new URL(url).pathname, "/health/latest.json");
      return new Response(accepted);
    },
  });

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Content-Type"), "application/json");
  assert.equal(response.headers.get("Cache-Control"), "public, max-age=300, stale-while-revalidate=60");
  assert.equal(await response.text(), accepted);
});

test("populated binding returns 200 and the exact bytes", async () => {
  const expected = new Uint8Array([0x7b, 0x22, 0x6f, 0x6b, 0x22, 0x3a, 0x74, 0x72, 0x75, 0x65, 0x7d]);
  const response = await request({
    get: async (key, type) => {
      assert.equal(key, "health-index.json");
      assert.equal(type, "arrayBuffer");
      return expected.buffer;
    },
  }, { fetch: async () => new Response("Not found", { status: 404 }) });

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Content-Type"), "application/json");
  assert.equal(response.headers.get("Cache-Control"), "public, max-age=300, stale-while-revalidate=60");
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
