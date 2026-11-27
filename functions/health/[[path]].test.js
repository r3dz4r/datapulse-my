import assert from "node:assert/strict";
import test from "node:test";

import { onRequest } from "./[[path]].js";

const request = (path, binding, assets) => onRequest({
  request: new Request(`https://data-pulse.test${path}`),
  env: { DATAPULSE_HEALTH_INDEX: binding, ASSETS: assets },
});

test("other health artifact returns exact KV bytes by URL-mirrored key", async () => {
  const expected = new TextEncoder().encode('{"datasets":[]}').buffer;
  const response = await request("/health/drift.json", {
    get: async (key, type) => {
      assert.equal(key, "health/drift.json");
      assert.equal(type, "arrayBuffer");
      return expected;
    },
  });

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Content-Type"), "application/json");
  assert.equal(response.headers.get("Cache-Control"), "public, max-age=300, stale-while-revalidate=60");
  assert.deepEqual(await response.arrayBuffer(), expected);
});

test("latest returns accepted static bytes ahead of newer KV", async () => {
  const accepted = '{"checked_at":"accepted"}';
  const response = await request("/health/latest.json", {
    get: async () => { throw new Error("KV must not be read"); },
  }, {
    fetch: async request => {
      assert.equal(new URL(request.url).pathname, "/health/latest.json");
      return new Response(accepted);
    },
  });

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Content-Type"), "application/json");
  assert.equal(response.headers.get("Cache-Control"), "public, max-age=300, stale-while-revalidate=60");
  assert.equal(await response.text(), accepted);
});

test("latest falls back to KV when the static asset is absent", async () => {
  const expected = '{"checked_at":"kv"}';
  const response = await request("/health/latest.json", {
    get: async key => {
      assert.equal(key, "health/latest.json");
      return new TextEncoder().encode(expected).buffer;
    },
  }, { fetch: async () => new Response("Not found", { status: 404 }) });

  assert.equal(response.status, 200);
  assert.equal(await response.text(), expected);
});

test("latest returns unavailable when static and KV are absent", async () => {
  const response = await request("/health/latest.json", { get: async () => null }, {
    fetch: async () => new Response("Not found", { status: 404 }),
  });

  assert.equal(response.status, 503);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.equal(await response.text(), '{"error":"health index unavailable"}');
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

test("accepted evidence returns the static asset bytes without touching KV", async () => {
  const evidence = '{"accepted":"signed-evidence"}';
  const assetPaths = [];
  const response = await request("/health/accepted/latest.json", {
    get: async () => { throw new Error("KV must not be read"); },
  }, {
    fetch: async request => {
      assetPaths.push(new URL(request.url).pathname);
      return new Response(evidence, { headers: { "Content-Type": "application/json" } });
    },
  });

  assert.equal(response.status, 200);
  assert.deepEqual(assetPaths, ["/health/accepted/latest.json"]);
  assert.equal(await response.text(), evidence);
});

test("accepted evidence absent from static assets returns the asset lookup's 404", async () => {
  const response = await request("/health/accepted/latest.json", {
    get: async () => { throw new Error("KV must not be read"); },
  }, { fetch: async () => new Response("asset not found", { status: 404 }) });

  assert.equal(response.status, 404);
  assert.equal(await response.text(), "asset not found");
});

test("sibling nested paths that are not the accepted evidence still return 404", async () => {
  const paths = [
    "/health/accepted/drift.json",
    "/health/accepted/latest.json.bak",
    "/health/accepted/",
    "/health/accepted",
    "/health/other/latest.json",
    "/health/accepted/latest.json/extra",
  ];
  for (const path of paths) {
    const response = await request(path, { get: async () => { throw new Error("must not read KV"); } }, {
      fetch: async () => { throw new Error(`must not fetch static asset for ${path}`); },
    });
    assert.equal(response.status, 404, path);
  }
});

test("traversal attempts under the accepted evidence name are refused", async () => {
  const paths = [
    "/health/accepted/..%2Flatest.json",
    "/health/accepted/latest.json/..%2F..%2Fdrift.json",
    "/health/accepted/latest.json%2F..%2F..%2Flatest.json",
  ];
  for (const path of paths) {
    const response = await request(path, { get: async () => { throw new Error("must not read KV"); } }, {
      fetch: async () => { throw new Error(`must not fetch static asset for ${path}`); },
    });
    assert.equal(response.status, 404, path);
  }
});

test("unknown or traversal-like paths are rejected", async () => {
  for (const path of ["/health/nope.json", "/health/../latest.json", "/other/latest.json"]) {
    const response = await request(path, { get: async () => { throw new Error("must not read KV"); } });
    assert.equal(response.status, 404);
  }
});
