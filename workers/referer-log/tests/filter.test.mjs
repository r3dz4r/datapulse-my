import assert from "node:assert/strict";
import test from "node:test";

import { buildNavigationRow } from "../src/filter.js";

function request(path, options = {}) {
  const result = new Request(`https://data-pulse.my${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: options.accept ?? "text/html,application/xhtml+xml",
      "Sec-Fetch-Mode": options.mode ?? "navigate",
      ...options.headers,
    },
  });
  Object.defineProperty(result, "cf", { value: options.cf });
  return result;
}

test("returns a row for an HTML document navigation", () => {
  const row = buildNavigationRow(request("/catalogue", {
    headers: { Referer: "https://example.com/page?q=secret" },
    cf: { country: "MY", colo: "KUL", deviceType: "mobile" },
  }));

  assert.deepEqual(row, {
    blobs: ["/catalogue", "example.com", "MY", "KUL", "mobile"],
  });
});

test("excludes Cloudflare RUM beacons", () => {
  assert.equal(buildNavigationRow(request("/cdn-cgi/rum")), null);
});

test("excludes MCP POST calls", () => {
  assert.equal(buildNavigationRow(request("/mcp", { method: "POST" })), null);
});

test("excludes static asset requests", () => {
  assert.equal(buildNavigationRow(request("/assets/datapulse.css")), null);
});

test("excludes HEAD requests", () => {
  assert.equal(buildNavigationRow(request("/catalogue", { method: "HEAD" })), null);
});

test("requires navigation mode and an HTML accept header", () => {
  assert.equal(buildNavigationRow(request("/catalogue", { mode: "cors" })), null);
  assert.equal(buildNavigationRow(request("/catalogue", { accept: "application/json" })), null);
});

test("stores a referer host only and no full IP field", () => {
  const row = buildNavigationRow(request("/", {
    headers: {
      Referer: "https://example.com/page?q=secret",
      "CF-Connecting-IP": "203.0.113.42",
    },
  }));

  assert.equal(row.blobs[1], "example.com");
  assert.equal(JSON.stringify(row).includes("secret"), false);
  assert.equal(Object.hasOwn(row, "ip"), false);
  assert.equal(JSON.stringify(row).includes("203.0.113.42"), false);
});
