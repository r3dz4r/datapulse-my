import assert from "node:assert/strict";
import test from "node:test";

import { onRequest } from "./[[path]].js";

const request = (path, binding, assets) => onRequest({
  request: new Request(`https://data-pulse.test${path}`),
  env: { DATAPULSE_HEALTH_INDEX: binding, ASSETS: assets },
});

test("health artifact returns exact KV bytes by URL-mirrored key", async () => {
  const expected = new TextEncoder().encode('{"datasets":[]}').buffer;
  const response = await request("/health/latest.json", {
    get: async (key, type) => {
      assert.equal(key, "health/latest.json");
      assert.equal(type, "arrayBuffer");
      return expected;
    },
  });

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Content-Type"), "application/json");
  assert.equal(response.headers.get("Cache-Control"), "public, max-age=60");
  assert.deepEqual(await response.arrayBuffer(), expected);
});

test("missing KV value falls back to the matching static asset", async () => {
  const response = await request("/health/drift.json", { get: async () => null }, {
    fetch: async request => new Response(`static:${new URL(request.url).pathname}`),
  });

  assert.equal(response.status, 200);
  assert.equal(await response.text(), "static:/health/drift.json");
});

test("missing binding retains the health index 503 contract", async () => {
  const response = await onRequest({ request: new Request("https://data-pulse.test/health/latest.json"), env: {} });

  assert.equal(response.status, 503);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.equal(await response.text(), '{"error":"health index unavailable"}');
});

test("unknown or traversal-like paths are rejected", async () => {
  for (const path of ["/health/nope.json", "/health/../latest.json", "/other/latest.json"]) {
    const response = await request(path, { get: async () => { throw new Error("must not read KV"); } });
    assert.equal(response.status, 404);
  }
});
